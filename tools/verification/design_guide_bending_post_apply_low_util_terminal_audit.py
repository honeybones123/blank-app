"""Focused live audit for low-util bending post-Apply terminal publication.

This verifier exercises one browser recipe, clicks the first Design Guide
action, and checks that a post-Apply all-pass low-util terminal card is backed
by exact/exhaustive cleanup evidence and does not leave the proof-pending shell
or an executable action button visible.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_family_browser_live_visual_consistency_snapshot import (  # noqa: E402
    _wait_for_final_design_guide_card,
)
from tools.verification.design_guide_browser_live_visual_consistency_snapshot import (  # noqa: E402
    _capture_visual_snapshot,
    _datetime_stamp,
    _stable_hash,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    TRACER_PATH,
    _query,
    _start_streamlit,
    _wait_for_http,
    _wait_for_run_end,
    _wait_for_solver_state,
)
from tools.verification.run_family_10_fuzz_audit import (  # noqa: E402
    _action_button_probe,
    _browser_recipe_error_from_state,
    _browser_recipe_from_state,
    _click_first_enabled_action,
    _extract_publication_probe,
    _post_apply_green_pass_visual_contract,
    _safe_dict,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
VISUAL_DIR = ROOT / "artifacts" / "reports" / "bending_post_apply_low_util_terminal"

LOW_UTIL_FLOOR = 0.85
LOADING_MARKERS = (
    "Checking design guidance",
    "Reviewing strength, detailing, serviceability, and cleanup options",
)


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        match = re.search(r"-?\d+(?:\.\d+)?", str(value))
        if not match:
            return None
        try:
            number = float(match.group(0))
        except ValueError:
            return None
    return number if number == number else None


def _walk_dicts(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        rows.append(value)
        for child in value.values():
            rows.extend(_walk_dicts(child))
    elif isinstance(value, list):
        for child in value:
            rows.extend(_walk_dicts(child))
    return rows


def _find_evidence_sources(browser_state: dict[str, Any], visual_snapshot: dict[str, Any]) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    for root in (browser_state, visual_snapshot):
        sources.extend(_walk_dicts(root))
    candidates: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        keys = set(source)
        if keys & {
            "best_safe_final_util",
            "target_band_search_exhaustive",
            "repair_or_target_band_search_exhaustive",
            "executable_target_band_candidate_count",
            "safe_bending_cleanup_count",
            "post_click_safe_bending_cleanup_count",
            "exact_blockers_by_family",
            "post_click_exact_blockers_by_family",
        }:
            candidates.append(dict(source))
    exhaustive_sources = [
        row
        for row in candidates
        if bool(
            row.get("target_band_search_exhaustive")
            or row.get("repair_or_target_band_search_exhaustive")
            or row.get("cleanup_search_exhaustive")
            or row.get("local_cleanup_search_exhaustive")
        )
    ]
    best_safe_values = [
        _number(row.get("best_safe_final_util"))
        for row in candidates
        if _number(row.get("best_safe_final_util")) is not None
    ]
    executable_target_counts = [
        int(float(row.get("executable_target_band_candidate_count") or 0))
        for row in candidates
        if "executable_target_band_candidate_count" in row
    ]
    return {
        "candidate_evidence_count": len(candidates),
        "exhaustive_evidence_count": len(exhaustive_sources),
        "best_safe_final_utils": best_safe_values[:12],
        "has_exhaustive_cleanup_evidence": bool(exhaustive_sources),
        "has_zero_executable_target_band_count": any(count == 0 for count in executable_target_counts),
        "sample_evidence": candidates[:5],
    }


def _visible_utilisation(text: str) -> float | None:
    for pattern in (
        r"utilisation\s*=\s*([0-9]+(?:\.[0-9]+)?)",
        r"Governing utilisation\s+([0-9]+(?:\.[0-9]+)?)",
        r"Expected util:\s*([0-9]+(?:\.[0-9]+)?)",
    ):
        match = re.search(pattern, text, re.I)
        if match:
            return _number(match.group(1))
    return None


def _classify_post_apply(
    *,
    before_state: dict[str, Any],
    after_state: dict[str, Any],
    post_apply_snapshot: dict[str, Any],
    run_end_event: dict[str, Any] | None,
    post_apply_card_probe: dict[str, Any],
    click_result: dict[str, Any],
) -> dict[str, Any]:
    design_guide = dict(post_apply_snapshot.get("design_guide") or {})
    text = str(design_guide.get("text_sample") or post_apply_card_probe.get("text_sample") or "")
    run_data = _safe_dict(_safe_dict(run_end_event).get("data"))
    evidence = _find_evidence_sources(after_state, post_apply_snapshot)
    green_contract = _post_apply_green_pass_visual_contract(post_apply_snapshot)
    visible_util = _visible_utilisation(text)
    low_util_pass = bool(green_contract.get("pass_visible")) and visible_util is not None and visible_util < LOW_UTIL_FLOOR
    pending_shell_visible = bool(
        green_contract.get("pending_shell_visible")
        or post_apply_card_probe.get("loading_shell_visible")
        or any(marker in text for marker in LOADING_MARKERS)
    )
    action_probe = _safe_dict(_safe_dict(post_apply_snapshot.get("checks")).get("cta"))
    action_buttons = list(action_probe.get("action_buttons") or [])
    enabled_action_buttons = [button for button in action_buttons if not bool(button.get("disabled"))]
    failures: list[str] = []
    warnings: list[str] = []
    if not click_result.get("clicked"):
        failures.append("initial_design_guide_action_not_clicked")
    if run_end_event is None:
        failures.append("apply_run_end_event_missing")
    elif run_data.get("all_key_pass") is not True:
        failures.append("post_apply_solver_not_all_key_pass")
    if pending_shell_visible:
        failures.append("post_apply_pending_shell_visible_with_final_card")
    if bool(green_contract.get("raw_status_visible")):
        failures.append("post_apply_raw_status_block_visible")
    if low_util_pass and not evidence.get("has_exhaustive_cleanup_evidence"):
        failures.append("low_util_pass_missing_exhaustive_cleanup_evidence")
    if low_util_pass and not evidence.get("has_zero_executable_target_band_count"):
        failures.append("low_util_pass_missing_zero_executable_target_band_count")
    if low_util_pass and enabled_action_buttons:
        failures.append("low_util_pass_still_has_enabled_action_button")
    if "current high shear demand" in text and _number(run_data.get("final_live_shear_util")) in (0.0, None):
        warnings.append("low_util_reason_mentions_high_shear_without_live_shear_util")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "warnings": warnings,
        "selected_family_before": _extract_publication_probe(before_state).get("selected_family_id"),
        "selected_family_after": _extract_publication_probe(after_state).get("selected_family_id"),
        "post_apply_all_key_pass": run_data.get("all_key_pass"),
        "post_apply_final_live_worst_util": run_data.get("final_live_worst_util"),
        "post_apply_final_live_bending_util": run_data.get("final_live_bending_util"),
        "post_apply_final_live_shear_util": run_data.get("final_live_shear_util"),
        "visible_utilisation": visible_util,
        "low_util_pass": low_util_pass,
        "pending_shell_visible": pending_shell_visible,
        "enabled_action_button_count": len(enabled_action_buttons),
        "green_pass_visual_contract": green_contract,
        "evidence": evidence,
        "text_hash": _stable_hash(text),
        "text_sample": text[:1800],
    }


def _run(args: argparse.Namespace) -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    process: subprocess.Popen | None = None
    started_process = False
    base_url = args.base_url or f"http://127.0.0.1:{int(args.port)}"
    try:
        if args.base_url:
            _wait_for_http(base_url)
        else:
            before_env = dict(os.environ)
            os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
            try:
                process = _start_streamlit(int(args.port))
                started_process = True
            finally:
                os.environ.clear()
                os.environ.update(before_env)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            context = browser.new_context(viewport={"width": 1600, "height": 1100})
            page = context.new_page()
            page.set_default_timeout(30_000)
            scenario_id = f"bending_post_apply_low_util_{_datetime_stamp()}"
            page.goto(
                _query(base_url, {"page": "inputs", "browser_recipe": args.recipe, "cid": scenario_id}),
                wait_until="domcontentloaded",
                timeout=90_000,
            )
            page.get_by_label("Browser state").wait_for(state="attached", timeout=45_000)
            before_card_probe = _wait_for_final_design_guide_card(page, timeout_s=float(args.card_timeout_s))
            before_snapshot = _capture_visual_snapshot(
                page,
                scenario_id=f"{scenario_id}_before",
                screenshot_path=VISUAL_DIR / f"{scenario_id}_before.png",
            )
            before_state = _safe_dict(before_snapshot.get("browser_state"))
            applied_recipe = _browser_recipe_from_state(before_state)
            recipe_error = _browser_recipe_error_from_state(before_state)
            button_probe_before = _action_button_probe(page)
            tracer_offset = TRACER_PATH.stat().st_size if TRACER_PATH.exists() else 0
            click_started_ms = int(time.time() * 1000)
            click_result = _click_first_enabled_action(page)
            after_state = before_state
            run_end_event = None
            solver_state_timeout = False
            if click_result.get("clicked"):
                after_state, solver_state_timeout = _wait_for_solver_state(
                    page,
                    timeout_ms=int(float(args.apply_timeout_s) * 1000),
                )
                run_end_event, _ = _wait_for_run_end(
                    tracer_offset,
                    timeout_s=float(args.apply_timeout_s),
                    start_time_ms=click_started_ms,
                )
            post_apply_card_probe = _wait_for_final_design_guide_card(page, timeout_s=float(args.card_timeout_s))
            post_apply_snapshot = _capture_visual_snapshot(
                page,
                scenario_id=f"{scenario_id}_post_apply",
                screenshot_path=VISUAL_DIR / f"{scenario_id}_post_apply.png",
            )
            after_state = _safe_dict(post_apply_snapshot.get("browser_state")) or after_state
            classification = _classify_post_apply(
                before_state=before_state,
                after_state=after_state,
                post_apply_snapshot=post_apply_snapshot,
                run_end_event=run_end_event,
                post_apply_card_probe=post_apply_card_probe,
                click_result=click_result,
            )
            context.close()
            browser.close()
            return {
                "schema": "design_guide_bending_post_apply_low_util_terminal_audit.v1",
                "status": classification["status"],
                "recipe": args.recipe,
                "base_url": base_url,
                "applied_recipe": applied_recipe,
                "recipe_error": recipe_error,
                "before_card_probe": before_card_probe,
                "post_apply_card_probe": post_apply_card_probe,
                "button_probe_before": button_probe_before,
                "click_result": click_result,
                "solver_state_timeout": bool(solver_state_timeout),
                "run_end_event": run_end_event,
                "publication_probe_before": _extract_publication_probe(before_state),
                "publication_probe_after": _extract_publication_probe(after_state),
                "classification": classification,
                "before_visual_hash": before_snapshot.get("scenario_hash"),
                "post_apply_visual_hash": post_apply_snapshot.get("scenario_hash"),
                "before_screenshot": str(VISUAL_DIR / f"{scenario_id}_before.png"),
                "post_apply_screenshot": str(VISUAL_DIR / f"{scenario_id}_post_apply.png"),
            }
    finally:
        if started_process and process is not None:
            try:
                process.terminate()
                process.wait(timeout=10)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Bending Post-Apply Low-Util Terminal Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Recipe: `{payload.get('recipe')}`",
        f"Applied recipe: `{payload.get('applied_recipe')}`",
        "",
        "## Result",
        "",
        f"- selected family before: `{cls.get('selected_family_before')}`",
        f"- selected family after: `{cls.get('selected_family_after')}`",
        f"- post-Apply all checks pass: `{cls.get('post_apply_all_key_pass')}`",
        f"- visible utilisation: `{cls.get('visible_utilisation')}`",
        f"- low-util PASS: `{cls.get('low_util_pass')}`",
        f"- pending shell visible: `{cls.get('pending_shell_visible')}`",
        f"- enabled action buttons after PASS: `{cls.get('enabled_action_button_count')}`",
        "",
        "## Failures",
        "",
        *[f"- `{failure}`" for failure in cls.get("failures") or ["none"]],
        "",
        "## Warnings",
        "",
        *[f"- `{warning}`" for warning in cls.get("warnings") or ["none"]],
        "",
        "## Evidence",
        "",
        f"- exhaustive cleanup evidence: `{(cls.get('evidence') or {}).get('has_exhaustive_cleanup_evidence')}`",
        f"- zero executable target-band count: `{(cls.get('evidence') or {}).get('has_zero_executable_target_band_count')}`",
        f"- best safe final utils: `{(cls.get('evidence') or {}).get('best_safe_final_utils')}`",
        "",
        "## Text Sample",
        "",
        "```text",
        str(cls.get("text_sample") or "")[:1800],
        "```",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8611)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--recipe", default="R1A_M300_V0")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--card-timeout-s", type=float, default=25.0)
    parser.add_argument("--apply-timeout-s", type=float, default=35.0)
    args = parser.parse_args()
    payload = _run(args)
    stamp = _datetime_stamp()
    artifact = ARTIFACT_DIR / f"design_guide_bending_post_apply_low_util_terminal_audit_{stamp}.json"
    report = AUDIT_DIR / f"design_guide_bending_post_apply_low_util_terminal_audit_{stamp}.md"
    artifact.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report, payload)
    print(f"design_guide_bending_post_apply_low_util_terminal_audit {payload.get('status')}")
    print(f"json={artifact}")
    print(f"report={report}")
    failures = (payload.get("classification") or {}).get("failures") or []
    if failures:
        print(f"failures={failures}")
    return 0 if payload.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
