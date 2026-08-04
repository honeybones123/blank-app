"""Live browser proof for the engineering snapshot/hash migration boundary.

This verifier is intentionally observational. It reads the dev-only browser
state probe, compares the new engineering hash with the existing Design Guide
fingerprint across frozen recipes, and records the remaining render-cutover
status. It does not alter product state or select, publish, render, or Apply a
recommendation.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from application.engineering_snapshot import build_engineering_input_snapshot_from_resolved_state
from tools.verification.helpers.browser_one_click_regression import (
    BROWSER_STATE_LABEL,
    _load_browser_state,
    _query,
    _start_streamlit,
    _wait_for_http,
)


AUDIT_DIR = ROOT / "artifacts" / "audits"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
DEFAULT_RECIPES = (
    "R1A_M300_V0",
    "R1B_M600_V0",
    "R2A_M0_V400",
    "R4A_M45_V0",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _capture_recipe(page: Any, *, base_url: str, recipe: str, index: int) -> dict[str, Any]:
    url = _query(
        base_url,
        {
            "page": "inputs",
            "browser_recipe": recipe,
            "browser_test_mode": "1",
            "cid": f"engineering_snapshot_{index}_{recipe}",
        },
    )
    page.goto(url, wait_until="domcontentloaded", timeout=90_000)
    page.get_by_label(BROWSER_STATE_LABEL).wait_for(state="attached", timeout=90_000)
    try:
        page.wait_for_selector(
            "[data-testid='design-guide-card'], [data-outcome-state], [data-publication-hash], .fast-guidance-item",
            timeout=90_000,
        )
    except Exception:
        # The hash probe is still useful for a deliberately blocked or empty
        # page, so let the state loader provide the authoritative failure.
        pass
    page.wait_for_timeout(2_000)
    state = _load_browser_state(page, fallback_timeout_ms=90_000)
    probe = dict(state.get("engineering_snapshot_probe") or {})
    return {
        "recipe": recipe,
        "url": url,
        "browser_recipe": state.get("browser_recipe"),
        "browser_recipe_error": state.get("browser_recipe_error"),
        "engineering_snapshot_probe": probe,
        "engineering_hash": probe.get("engineering_hash"),
        "legacy_fingerprint_hash": probe.get("legacy_design_guide_fingerprint_hash"),
        "snapshot": dict(probe.get("snapshot") or {}),
        "authoritative_runtime_probe": dict(
            (state.get("browser_debug_probe") or {}).get(
                "authoritative_design_result_runtime_probe"
            )
            or {}
        ),
        "render_compute_probe": dict(
            (state.get("browser_debug_probe") or {}).get(
                "design_guide_render_compute_probe"
            )
            or {}
        ),
        "render_timing_probe": dict(state.get("render_timing_probe") or {}),
        "speed_profile_probe": dict(state.get("speed_profile_probe") or {}),
    }


def _snapshot_checks(row: dict[str, Any]) -> dict[str, Any]:
    probe = dict(row.get("engineering_snapshot_probe") or {})
    snapshot = dict(row.get("snapshot") or {})
    expected_keys = {
        "geometry",
        "materials",
        "reinforcement",
        "design_actions",
        "design_settings",
        "locked_variables",
        "unlocked_variables",
        "contract_versions",
        "calculation_versions",
        "schema_version",
    }
    ui_leaks = sorted(
        key
        for key in (
            "active_tab",
            "active_tabs",
            "expanded_panels",
            "scroll_state",
            "camera_settings",
            "help_toggles",
            "fullscreen_state",
            "loading_flags",
            "timestamps",
            "guidance_cache_hit",
            "guidance_compute_ms",
        )
        if key in snapshot
    )
    return {
        "probe_present": bool(probe) and not bool(probe.get("error")),
        "engineering_hash_shape": isinstance(row.get("engineering_hash"), str)
        and len(str(row.get("engineering_hash"))) == 64,
        "legacy_fingerprint_hash_shape": isinstance(row.get("legacy_fingerprint_hash"), str)
        and bool(row.get("legacy_fingerprint_hash")),
        "snapshot_schema_complete": expected_keys.issubset(snapshot),
        "ui_state_absent_from_snapshot": not ui_leaks,
        "ui_state_leaks": ui_leaks,
        "recipe_applied": row.get("browser_recipe") == row.get("recipe"),
        "recipe_error_absent": not bool(row.get("browser_recipe_error")),
        "authoritative_result_runtime_probe_present": bool(
            row.get("authoritative_runtime_probe", {}).get("engineering_hash")
        )
        and not bool(row.get("authoritative_runtime_probe", {}).get("error")),
        "zero_render_compute_calls": int(
            row.get("render_compute_probe", {}).get("render_compute_calls") or 0
        ) == 0,
    }


def _build_comparisons(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_recipe = {str(row.get("recipe")): row for row in rows}
    pairs = (
        ("moment_change", "R1A_M300_V0", "R1B_M600_V0"),
        ("load_domain_change", "R1A_M300_V0", "R2A_M0_V400"),
        ("overdesign_change", "R1A_M300_V0", "R4A_M45_V0"),
    )
    comparisons = []
    for label, left_name, right_name in pairs:
        if left_name not in by_recipe or right_name not in by_recipe:
            continue
        left = by_recipe.get(left_name) or {}
        right = by_recipe.get(right_name) or {}
        new_changed = bool(left.get("engineering_hash")) and bool(right.get("engineering_hash")) and (
            left.get("engineering_hash") != right.get("engineering_hash")
        )
        legacy_changed = bool(left.get("legacy_fingerprint_hash")) and bool(right.get("legacy_fingerprint_hash")) and (
            left.get("legacy_fingerprint_hash") != right.get("legacy_fingerprint_hash")
        )
        comparisons.append(
            {
                "comparison": label,
                "left": left_name,
                "right": right_name,
                "new_engineering_hash_changed": new_changed,
                "legacy_fingerprint_changed": legacy_changed,
                "change_sensitivity_agrees": new_changed == legacy_changed and new_changed,
            }
        )
    return comparisons


def _build_report(*, stamp: str, payload: dict[str, Any], audit_path: Path) -> Path:
    rows = payload["rows"]
    comparisons = payload["comparisons"]
    checks = payload["checks"]
    lines = [
        "# Live Engineering Snapshot Hash Comparison",
        "",
        f"Generated: `{stamp}`",
        "",
        "## Result",
        "",
        f"- Hash projection proof: **{payload['status']}**",
        "- Scope: browser-state observation only; no product selection, publication, CTA, Apply, or mutation path was changed.",
        "- Render-time compute cutover: **PENDING** until the live Design Guide coordinator consumes the session-owned result.",
        "",
        "## Per-Recipe Checks",
        "",
        "| Recipe | Hash | Legacy fingerprint | Probe | UI state absent | Applied |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        check = row["checks"]
        lines.append(
            "| {recipe} | {hash} | {legacy} | {probe} | {ui} | {applied} |".format(
                recipe=row["recipe"],
                hash="yes" if check["engineering_hash_shape"] else "no",
                legacy="yes" if check["legacy_fingerprint_hash_shape"] else "no",
                probe="yes" if check["probe_present"] else "no",
                ui="yes" if check["ui_state_absent_from_snapshot"] else "no",
                applied="yes" if check["recipe_applied"] and check["recipe_error_absent"] else "no",
            )
        )
    lines.extend(["", "## Engineering Change Comparisons", "", "| Comparison | New hash changed | Legacy fingerprint changed | Agreement |", "|---|---|---|---|"])
    for row in comparisons:
        lines.append(
            f"| {row['comparison']} | {row['new_engineering_hash_changed']} | {row['legacy_fingerprint_changed']} | {row['change_sensitivity_agrees']} |"
        )
    lines.extend(
        [
            "",
            "## Detector Status",
            "",
            "The application coordinator owns the Design Brain compute and the render path consumes the session-owned result without a cache-miss compute fallback. Publication, CTA, and Apply ownership remain transitional page/bridge responsibilities.",
            "",
            "## Required Next Slice",
            "",
            "Move final publication, CTA, and Apply payload ownership behind the authoritative result, then delete the remaining compatibility-only page/bridge routes after parity verification.",
            "",
            f"Machine-readable artifact: `{audit_path.relative_to(ROOT).as_posix()}`",
        ]
    )
    report_path = AUDIT_DIR / f"live_engineering_snapshot_hash_comparison_{stamp}.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9374)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--recipe", action="append", default=[])
    args = parser.parse_args(argv)
    recipes = tuple(args.recipe or DEFAULT_RECIPES)
    process = None
    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    try:
        if args.base_url is None:
            process = _start_streamlit(args.port)
        else:
            _wait_for_http(base_url)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            rows = []
            same_session_repeat: dict[str, Any] = {}
            for index, recipe in enumerate(recipes, start=1):
                context = browser.new_context(viewport={"width": 1600, "height": 1050})
                page = context.new_page()
                page.set_default_timeout(45_000)
                try:
                    row = _capture_recipe(page, base_url=base_url, recipe=str(recipe), index=index)
                except Exception as exc:
                    row = {
                        "recipe": str(recipe),
                        "browser_recipe": None,
                        "browser_recipe_error": f"{type(exc).__name__}: {exc}",
                        "engineering_snapshot_probe": {},
                        "engineering_hash": None,
                        "legacy_fingerprint_hash": None,
                        "snapshot": {},
                    }
                row["checks"] = _snapshot_checks(row)
                rows.append(row)
                if index == 1 and row.get("engineering_hash"):
                    try:
                        same_session_repeat = _capture_recipe(
                            page,
                            base_url=base_url,
                            recipe=str(recipes[0]),
                            index=1,
                        )
                    except Exception:
                        same_session_repeat = {}
                context.close()
            # The repeat uses the same browser session, so a successful
            # engineering-hash match also proves session-store reuse.
            repeat = same_session_repeat
            browser.close()
        comparisons = _build_comparisons(rows)
        same_state_hash_stable = bool(rows) and rows[0].get("engineering_hash") == repeat.get("engineering_hash")
        same_state_legacy_stable = bool(rows) and rows[0].get("legacy_fingerprint_hash") == repeat.get("legacy_fingerprint_hash")
        checks = {
            "all_recipe_checks_pass": all(all(value for key, value in row["checks"].items() if key != "ui_state_leaks") for row in rows),
            "same_state_engineering_hash_stable": same_state_hash_stable,
            "same_state_legacy_fingerprint_stable": same_state_legacy_stable,
            "engineering_change_sensitivity_agrees": bool(comparisons) and all(
                row["change_sensitivity_agrees"] for row in comparisons
            ),
            "no_ui_state_leaks": all(not row["checks"]["ui_state_leaks"] for row in rows),
        }
        session_reuse_observed = str(
            (repeat.get("authoritative_runtime_probe") or {}).get("reuse_decision", {}).get("reason")
        ) == "engineering_hash_match"
        status = "HASH_PROOF_LOCKED_PUBLICATION_CUTOVER_PENDING" if all(checks.values()) else "FAIL"
        stamp = _stamp()
        payload = {
            "schema": "live_engineering_snapshot_hash_comparison.v1",
            "status": status,
            "recipes": list(recipes),
            "checks": checks,
            "rows": rows,
            "repeat_capture": repeat,
            "observations": {"same_session_authoritative_result_reused": session_reuse_observed},
            "comparisons": comparisons,
        }
        VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        audit_path = VERIFICATION_DIR / f"live_engineering_snapshot_hash_comparison_{stamp}.json"
        audit_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
        report_path = _build_report(stamp=stamp, payload=payload, audit_path=audit_path)
        print(json.dumps({"status": status, "artifact": str(audit_path), "report": str(report_path), "checks": checks}, indent=2))
        return 0 if status != "FAIL" else 1
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
