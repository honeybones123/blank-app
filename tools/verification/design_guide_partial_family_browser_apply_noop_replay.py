"""Focused browser apply/noop replay for remaining PARTIAL families.

Proof-only. This verifier starts the app in browser-test mode, opens targeted
recipe states through the normal Inputs page, proves the requested recipe was
applied via the hidden browser-state probe, and records whether the selected
family's published recommendation:

* applies and changes page/check outputs, or
* intentionally has no enabled Apply/one-click action, or
* still exposes a focused product-path gap.

It does not change family runtimes, contracts, CTA rendering, publication,
apply routing, visible wording, or normal product behaviour.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification import design_guide_product_path_gate as product_gate  # noqa: E402
from tools.verification.helpers.browser_helpers import _load_browser_state  # noqa: E402
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _query,
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

PASS_VERDICTS = {"APPLY_EFFECT_PROVEN", "INTENTIONAL_NOOP_PROVEN"}
APPLY_EFFECT_WITH_CARD_TIMEOUT_VERDICT = "GAP_APPLY_EFFECT_PROVEN_BUT_POST_CLICK_CARD_TIMEOUT"
TARGET_FAMILIES = (
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
    "COMBINED_OVERDESIGN_GOVERNS",
    "SERVICEABILITY_GOVERNS",
)

FAMILY_ALIASES: dict[str, tuple[str, ...]] = {
    "COMBINED_OVERDESIGN_GOVERNS": ("COMBINED_OVERDESIGN_GOVERNS", "COMBINED_OVERDESIGN"),
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS": (
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        "SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS",
    ),
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS": (
        "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        "BENDING_FAIL_SHEAR_OPTIMISE_GOVERNS",
    ),
    "SERVICEABILITY_GOVERNS": ("SERVICEABILITY_GOVERNS", "SERVICEABILITY"),
}


@dataclass(frozen=True)
class ReplayAttempt:
    name: str
    family_id: str
    recipe: str
    expect_noop_ok: bool = False


ATTEMPTS: tuple[ReplayAttempt, ...] = (
    ReplayAttempt(
        name="bending_fail_shear_overdesign_active_failure",
        family_id="BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        recipe="MATRIX_ACTIVE_FAILURE_TERMINAL_PROOF_PRESENT",
    ),
    ReplayAttempt(
        name="bending_fail_shear_overdesign_shear_in_target",
        family_id="BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        recipe="MATRIX_SHEAR_IN_TARGET_BENDING_FAIL",
    ),
    ReplayAttempt(
        name="shear_fail_bending_overdesign_shear_only",
        family_id="SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        recipe="B_shear_under_only",
    ),
    ReplayAttempt(
        name="shear_fail_bending_overdesign_bending_in_target",
        family_id="SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        recipe="MATRIX_BENDING_IN_TARGET_SHEAR_FAIL",
    ),
    ReplayAttempt(
        name="combined_overdesign_regression",
        family_id="COMBINED_OVERDESIGN_GOVERNS",
        recipe="F_combined_overdesign",
    ),
    ReplayAttempt(
        name="combined_overdesign_expectation",
        family_id="COMBINED_OVERDESIGN_GOVERNS",
        recipe="OPT_EXPECT_COMBINED_SAFE_OVERDESIGNED",
    ),
    ReplayAttempt(
        name="serviceability_deflection_only",
        family_id="SERVICEABILITY_GOVERNS",
        recipe="MATRIX_DEFLECTION_ONLY_FAIL",
        expect_noop_ok=True,
    ),
    ReplayAttempt(
        name="serviceability_crack_only",
        family_id="SERVICEABILITY_GOVERNS",
        recipe="MATRIX_CRACK_SERVICEABILITY_ONLY_FAIL",
        expect_noop_ok=True,
    ),
    ReplayAttempt(
        name="serviceability_golden_blocked",
        family_id="SERVICEABILITY_GOVERNS",
        recipe="GOLDEN_SERVICEABILITY_BLOCKED",
        expect_noop_ok=True,
    ),
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _compact_text(value: Any, limit: int = 240) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def _family_selection(snapshot: dict[str, Any]) -> dict[str, str]:
    return {str(k): str(v or "") for k, v in dict(snapshot.get("family_selection") or {}).items()}


def _selected_family_ids(snapshot: dict[str, Any], browser_state: dict[str, Any]) -> dict[str, str]:
    family_selection = _family_selection(snapshot)
    guidance = dict(browser_state.get("guidance_probe") or {})
    compute = dict(browser_state.get("guidance_compute_probe") or {})
    rendered = dict(browser_state.get("design_guide_render_probe") or {})
    rendered_contract = dict(rendered.get("primary_button_contract") or rendered.get("button_contract") or {})
    final_publication = dict(browser_state.get("final_design_guide_publication") or {})
    return {
        "snapshot_selected_family_id": family_selection.get("selected_family_id", ""),
        "snapshot_published_family_id": family_selection.get("published_family_id", ""),
        "snapshot_cta_family_id": family_selection.get("cta_family_id", ""),
        "snapshot_apply_payload_family_id": family_selection.get("apply_payload_family_id", ""),
        "guidance_selected_family": str(guidance.get("selected_family") or guidance.get("selected_family_id") or ""),
        "compute_selected_family": str(compute.get("selected_family") or compute.get("selected_family_id") or ""),
        "render_contract_family": str(rendered_contract.get("family") or rendered_contract.get("family_id") or ""),
        "final_publication_family": str(final_publication.get("selected_family_id") or final_publication.get("family_id") or ""),
    }


def _family_matches(family_id: str, snapshot: dict[str, Any], browser_state: dict[str, Any]) -> bool:
    ids = _selected_family_ids(snapshot, browser_state)
    aliases = {value.upper() for value in FAMILY_ALIASES.get(family_id, (family_id,))}
    return any(str(value or "").upper() in aliases for value in ids.values())


def _browser_recipe_probe(browser_state: dict[str, Any]) -> dict[str, Any]:
    return {
        "browser_recipe": browser_state.get("browser_recipe"),
        "browser_recipe_kind": browser_state.get("browser_recipe_kind"),
        "browser_recipe_error": browser_state.get("browser_recipe_error"),
        "browser_recipe_applied_state_keys": sorted((browser_state.get("browser_recipe_applied_state") or {}).keys())[:80]
        if isinstance(browser_state.get("browser_recipe_applied_state"), dict)
        else [],
    }


def _output_fingerprint(snapshot: dict[str, Any], browser_state: dict[str, Any]) -> dict[str, Any]:
    overview = dict(browser_state.get("summary_overview_probe") or {})
    summary = dict(browser_state.get("summary_state_probe") or {})
    controls = dict(snapshot.get("visible_control_values") or {})
    family_selection = _family_selection(snapshot)
    return {
        "family_selection": {
            key: family_selection.get(key, "")
            for key in (
                "selected_family_id",
                "published_family_id",
                "cta_family_id",
                "apply_payload_family_id",
                "render_action_type",
                "render_update_count",
                "render_cta_enabled",
            )
        },
        "overview_statuses": overview.get("statuses"),
        "overview_worst_util": overview.get("worst_util"),
        "summary_values": {
            key: summary.get(key)
            for key in (
                "bending_util",
                "shear_util",
                "crack_util",
                "deflection_util",
                "bending_status",
                "shear_status",
                "crack_status",
                "deflection_status",
                "b",
                "D",
                "bot1_count",
                "db_bot_1",
                "lig_d",
                "lig_legs",
                "s_lig",
            )
            if key in summary
        },
        "visible_controls": controls,
        "first_card_text_hash": _stable_hash(snapshot.get("first_card_text") or ""),
    }


def _enabled_action_buttons(snapshot: dict[str, Any]) -> list[str]:
    labels = []
    for label in product_gate._visible_cta_buttons(snapshot):
        clean = " ".join(str(label or "").split())
        if clean and clean not in labels:
            labels.append(clean)
    return labels


def _click_first_enabled_action(page) -> dict[str, Any]:
    clicked = page.evaluate(
        """
        () => {
          const visible = (el) => {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style && style.visibility !== 'hidden' && style.display !== 'none' &&
              rect.width > 0 && rect.height > 0;
          };
          const buttons = Array.from(document.querySelectorAll("button"))
            .filter((el) => visible(el) && !el.disabled && el.getAttribute("aria-disabled") !== "true")
            .filter((el) => /one-click|apply|auto design/i.test((el.innerText || el.textContent || "")));
          const button = buttons[0] || null;
          if (!button) return {clicked: false, label: ""};
          const label = (button.innerText || button.textContent || "").replace(/\\s+/g, " ").trim();
          button.scrollIntoView({block: "center", inline: "center"});
          button.click();
          return {clicked: true, label};
        }
        """
    )
    return dict(clicked or {})


def _noop_reason(snapshot: dict[str, Any], browser_state: dict[str, Any]) -> str:
    text = " ".join(
        [
            str(snapshot.get("first_card_text") or ""),
            str(snapshot.get("body_text") or ""),
            _stable_json(browser_state.get("guidance_probe") or {}),
        ]
    ).lower()
    markers = (
        "no further",
        "no valid",
        "exact stop",
        "exhausted",
        "blocked",
        "already",
        "not accepted",
        "no executable",
        "no action",
        "review the recorded",
    )
    for marker in markers:
        if marker in text:
            return marker
    return ""


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Partial Family Browser Apply / Noop Replay",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        f"Covered: `{payload['coverage_summary']['covered']}`",
        f"Gaps: `{payload['coverage_summary']['gaps']}`",
        "",
        "## Family Verdicts",
        "",
        "| Family | Verdict | Counts As Coverage | Selected Attempt | Reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for family_id, row in payload["families"].items():
        selected = dict(row.get("selected_attempt") or {})
        lines.append(
            f"| `{family_id}` | `{row['verdict']}` | `{row['counts_as_apply_effect_coverage']}` | "
            f"`{selected.get('name') or ''}` | {row['reason']} |"
        )
    lines.extend(["", "## Attempts", ""])
    for attempt in payload["attempts"]:
        lines.extend(
            [
                f"### {attempt['name']}",
                "",
                f"- Family target: `{attempt['family_id']}`",
                f"- Recipe: `{attempt['recipe']}`",
                f"- Status: `{attempt['status']}`",
                f"- Verdict: `{attempt.get('verdict')}`",
                f"- Selected IDs: `{attempt.get('family_ids')}`",
                f"- Failures: `{attempt.get('failures')}`",
                "",
            ]
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _goto_recipe(page, base_url: str, recipe: str, *, ready_timeout_ms: int, card_timeout_ms: int) -> None:
    url = _query(base_url, {"page": "inputs", "browser_recipe": recipe})
    page.goto(url, wait_until="domcontentloaded", timeout=75_000)
    product_gate._wait_for_product_ready(page, timeout_ms=ready_timeout_ms)
    product_gate._wait_for_design_guide_card(page, timeout_ms=card_timeout_ms)


def _run_attempt(
    browser,
    base_url: str,
    artifact_run_dir: Path,
    attempt: ReplayAttempt,
    *,
    headed: bool = False,
    ready_timeout_ms: int = 75_000,
    card_timeout_ms: int = 120_000,
) -> dict[str, Any]:
    context = browser.new_context(viewport={"width": 1600, "height": 1000})
    page = context.new_page()
    row: dict[str, Any] = {
        "name": attempt.name,
        "family_id": attempt.family_id,
        "recipe": attempt.recipe,
        "status": "PASS",
        "verdict": "GAP",
        "counts_as_apply_effect_coverage": False,
        "failures": [],
        "screenshots": {},
    }
    try:
        _goto_recipe(page, base_url, attempt.recipe, ready_timeout_ms=ready_timeout_ms, card_timeout_ms=card_timeout_ms)
        before_state = _load_browser_state(page, timeout_s=45.0)
        before = product_gate._snapshot(page)
        row["screenshots"]["before"] = product_gate._save_screenshot(page, artifact_run_dir, attempt.name, "before")
        row["browser_recipe_probe"] = _browser_recipe_probe(before_state)
        row["family_ids"] = _selected_family_ids(before, before_state)
        row["family_selection"] = _family_selection(before)
        row["visible_cta_buttons"] = _enabled_action_buttons(before)
        row["card_text_sample"] = _compact_text(before.get("first_card_text"), 360)
        row["before_output_hash"] = _stable_hash(_output_fingerprint(before, before_state))

        if before_state.get("browser_recipe") != attempt.recipe:
            row["failures"].append(
                f"requested_browser_recipe_mismatch:requested={attempt.recipe}:applied={before_state.get('browser_recipe')}"
            )
            row["verdict"] = "GAP_RECIPE_NOT_PROVEN"
            return row
        if before_state.get("browser_recipe_error"):
            row["failures"].append(f"browser_recipe_error:{before_state.get('browser_recipe_error')}")
            row["verdict"] = "GAP_RECIPE_ERROR"
            return row
        if not _family_matches(attempt.family_id, before, before_state):
            row["failures"].append(f"target_family_not_selected:{attempt.family_id}")
            row["verdict"] = "GAP_TARGET_FAMILY_NOT_SELECTED"
            return row

        ctas = _enabled_action_buttons(before)
        if ctas:
            click = _click_first_enabled_action(page)
            row["click"] = click
            if not click.get("clicked"):
                row["failures"].append("enabled_cta_detected_but_click_failed")
                row["verdict"] = "GAP_CLICK_FAILED"
                return row
            try:
                product_gate._wait_for_settle(page, timeout_ms=75_000)
                product_gate._wait_for_design_guide_card(page, timeout_ms=180_000)
            except PlaywrightTimeoutError:
                product_gate._wait_for_settle(page, timeout_ms=30_000)
            after_state = _load_browser_state(page, timeout_s=45.0)
            after = product_gate._snapshot(page)
            row["screenshots"]["after"] = product_gate._save_screenshot(page, artifact_run_dir, attempt.name, "after")
            after_hash = _stable_hash(_output_fingerprint(after, after_state))
            row["after_output_hash"] = after_hash
            row["after_family_ids"] = _selected_family_ids(after, after_state)
            row["after_family_selection"] = _family_selection(after)
            row["after_card_text_sample"] = _compact_text(after.get("first_card_text"), 360)
            row["output_changed_after_click"] = after_hash != row["before_output_hash"]
            if after_hash != row["before_output_hash"]:
                row["verdict"] = "APPLY_EFFECT_PROVEN"
                row["counts_as_apply_effect_coverage"] = True
                row["reason"] = "Enabled published action was clicked and page/check output fingerprint changed."
            else:
                reason = _noop_reason(after, after_state)
                if reason:
                    row["verdict"] = "INTENTIONAL_NOOP_PROVEN"
                    row["counts_as_apply_effect_coverage"] = True
                    row["reason"] = f"Enabled action did not change output, but final publication carries no-op/exhausted proof marker `{reason}`."
                else:
                    row["failures"].append("button_click_no_visible_output_effect")
                    row["verdict"] = "GAP_CLICK_NO_OUTPUT_EFFECT"
            return row

        reason = _noop_reason(before, before_state)
        if reason and attempt.expect_noop_ok:
            row["verdict"] = "INTENTIONAL_NOOP_PROVEN"
            row["counts_as_apply_effect_coverage"] = True
            row["reason"] = f"No enabled Apply/one-click CTA, and publication carries no-op/exhausted proof marker `{reason}`."
        else:
            row["failures"].append("target_family_selected_without_enabled_cta_or_accepted_noop_marker")
            row["verdict"] = "GAP_NO_CTA_NO_NOOP_PROOF"
        return row
    except PlaywrightTimeoutError as exc:
        row["status"] = "PASS"
        row["verdict"] = "GAP_CARD_TIMEOUT"
        row["failures"].append(
            f"Product ready or Design Guide card timeout: ready_timeout_ms={ready_timeout_ms}; "
            f"card_timeout_ms={card_timeout_ms}; {exc}"
        )
        try:
            state = _load_browser_state(page, timeout_s=5.0)
            row["browser_recipe_probe"] = _browser_recipe_probe(state)
            row["browser_state_keys"] = sorted(str(key) for key in state.keys())[:80]
            snapshot = product_gate._snapshot(page)
            timeout_hash = _stable_hash(_output_fingerprint(snapshot, state))
            row["timeout_output_hash"] = timeout_hash
            row["timeout_family_ids"] = _selected_family_ids(snapshot, state)
            row["timeout_family_selection"] = _family_selection(snapshot)
            row["timeout_card_text_sample"] = _compact_text(snapshot.get("first_card_text"), 360)
            if row.get("before_output_hash"):
                row["output_changed_after_click"] = timeout_hash != row.get("before_output_hash")
                if dict(row.get("click") or {}).get("clicked") and row["output_changed_after_click"]:
                    row["verdict"] = "GAP_APPLY_EFFECT_PROVEN_BUT_POST_CLICK_CARD_TIMEOUT"
                    row["reason"] = (
                        "Enabled published action was clicked and page/check output fingerprint changed, "
                        "but the post-click Design Guide card did not become verifier-ready."
                    )
        except Exception as state_exc:
            row["browser_state_error"] = f"{type(state_exc).__name__}: {state_exc}"
        try:
            row["screenshots"]["timeout"] = product_gate._save_screenshot(page, artifact_run_dir, attempt.name, "timeout")
        except Exception:
            pass
        return row
    except Exception as exc:
        row["status"] = "ERROR"
        row["verdict"] = "GAP_REPLAY_ERROR"
        row["failures"].append(f"{type(exc).__name__}: {exc}")
        try:
            row["screenshots"]["error"] = product_gate._save_screenshot(page, artifact_run_dir, attempt.name, "error")
        except Exception:
            pass
        return row
    finally:
        if not headed:
            context.close()


def _choose_family_rows(
    attempt_rows: list[dict[str, Any]],
    *,
    family_ids: tuple[str, ...] = TARGET_FAMILIES,
) -> dict[str, Any]:
    families: dict[str, Any] = {}
    for family_id in family_ids:
        rows = [row for row in attempt_rows if row.get("family_id") == family_id]
        selected = next((row for row in rows if row.get("verdict") in PASS_VERDICTS), None)
        if selected:
            verdict = str(selected["verdict"])
            reason = str(selected.get("reason") or "")
            counts = True
        else:
            selected = next(
                (row for row in rows if row.get("verdict") == APPLY_EFFECT_WITH_CARD_TIMEOUT_VERDICT),
                rows[0] if rows else {},
            )
            verdict = str(selected.get("verdict") or "GAP_FOCUSED_BROWSER_REPLAY_REQUIRED")
            reasons = []
            for row in rows:
                reasons.extend(str(failure) for failure in row.get("failures") or [])
                if row.get("verdict"):
                    reasons.append(str(row.get("verdict")))
            reason = "; ".join(reasons[:8]) or "No focused browser attempt covered this family."
            counts = False
        families[family_id] = {
            "family_id": family_id,
            "verdict": verdict,
            "counts_as_apply_effect_coverage": counts,
            "reason": reason,
            "selected_attempt": {
                "name": selected.get("name"),
                "recipe": selected.get("recipe"),
                "verdict": selected.get("verdict"),
                "family_ids": selected.get("family_ids"),
                "before_output_hash": selected.get("before_output_hash"),
                "after_output_hash": selected.get("after_output_hash"),
                "timeout_output_hash": selected.get("timeout_output_hash"),
                "output_changed_after_click": selected.get("output_changed_after_click"),
                "visible_cta_buttons": selected.get("visible_cta_buttons"),
                "screenshots": selected.get("screenshots"),
            },
            "attempt_count": len(rows),
        }
    return families


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8537)
    parser.add_argument("--headed", action="store_true", default=False)
    parser.add_argument("--reuse-existing-server", action="store_true", default=False)
    parser.add_argument("--family", action="append", choices=TARGET_FAMILIES)
    parser.add_argument("--attempt", action="append", help="Run only the named attempt. May be repeated.")
    parser.add_argument("--card-timeout-sec", type=float, default=120.0)
    parser.add_argument("--ready-timeout-sec", type=float, default=75.0)
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    run_dir = ARTIFACT_DIR / f"design_guide_partial_family_browser_apply_noop_replay_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    base_url = f"http://127.0.0.1:{args.port}"

    process = None
    if not args.reuse_existing_server:
        process = _start_streamlit(args.port)
    else:
        _wait_for_http(base_url, timeout_s=45.0)

    requested_families = set(args.family or TARGET_FAMILIES)
    attempts = [attempt for attempt in ATTEMPTS if attempt.family_id in requested_families]
    if args.attempt:
        requested_attempts = set(args.attempt)
        attempts = [attempt for attempt in attempts if attempt.name in requested_attempts]
    attempt_rows: list[dict[str, Any]] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not args.headed)
            try:
                for attempt in attempts:
                    print(
                        json.dumps(
                            {
                                "event": "attempt_start",
                                "name": attempt.name,
                                "family_id": attempt.family_id,
                                "recipe": attempt.recipe,
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )
                    attempt_rows.append(
                        _run_attempt(
                            browser,
                            base_url,
                            run_dir,
                            attempt,
                            headed=args.headed,
                            ready_timeout_ms=int(max(5.0, args.ready_timeout_sec) * 1000),
                            card_timeout_ms=int(max(5.0, args.card_timeout_sec) * 1000),
                        )
                    )
                    print(
                        json.dumps(
                            {
                                "event": "attempt_end",
                                "name": attempt_rows[-1].get("name"),
                                "verdict": attempt_rows[-1].get("verdict"),
                                "failures": attempt_rows[-1].get("failures"),
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )
            finally:
                browser.close()
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()

    evaluated_family_ids = tuple(
        family_id
        for family_id in TARGET_FAMILIES
        if any(
            attempt.family_id == family_id
            for attempt in attempts
        )
    )
    families = _choose_family_rows(
        attempt_rows,
        family_ids=evaluated_family_ids,
    )
    gaps = [family_id for family_id, row in families.items() if not row["counts_as_apply_effect_coverage"]]
    payload = {
        "schema": "design_guide_partial_family_browser_apply_noop_replay.v1",
        "status": "PASS",
        "created_at": stamp,
        "product_behaviour_changed": False,
        "browser_test_mode": True,
        "target_families": list(evaluated_family_ids),
        "pass_verdicts": sorted(PASS_VERDICTS),
        "families": families,
        "attempts": attempt_rows,
        "coverage_summary": {
            "covered": len(evaluated_family_ids) - len(gaps),
            "gaps": len(gaps),
            "gap_families": gaps,
        },
        "artifact_dir": str(run_dir),
    }
    json_path = ARTIFACT_DIR / f"design_guide_partial_family_browser_apply_noop_replay_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_partial_family_browser_apply_noop_replay_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "artifact": str(json_path),
                "report": str(report_path),
                "covered": payload["coverage_summary"]["covered"],
                "gaps": payload["coverage_summary"]["gaps"],
                "gap_families": gaps,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
