"""Representative-family browser/live Design Guide visual consistency snapshot.

Proof-only verifier. It samples representative browser recipes and reuses the
single-scenario live visual consistency capture to check visible Design Guide
card structure, tone, CTA state, fallback/stale markers, and publication hash
exposure across several family classes.

It does not change product behaviour, family runtimes, contracts, CTA/apply
routing, visible wording, calculations, widget keys, or render ownership.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_browser_live_visual_consistency_snapshot import (  # noqa: E402
    _capture_visual_snapshot,
    _datetime_stamp,
    _design_guide_section,
    _latest_artifact,
    _stable_hash,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _query,
    _start_streamlit,
    _wait_for_http,
)
from tools.verification.recipes.one_click_recipe_defs import (  # noqa: E402
    DEBUG_CASES,
    FROZEN_RECIPES,
    REGRESSION_CASES,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

FINAL_CARD_MARKERS = (
    "Design is efficient",
    "Strengthening required",
    "Design accepted - target band achieved",
    "Design Guide blocker proof incomplete",
    "Repair required",
    "Why action is required",
    "Why repair is blocked",
    "Why no further cleanup?",
    "Preview after proposed change",
    "All checks pass",
    "cleanup blocked",
)
LOADING_SHELL_MARKERS = (
    "Checking design guidance",
    "Reviewing strength, detailing, serviceability, and cleanup options",
    "StrengthDetailingServiceabilityCleanup options",
)

NON_VISUAL_WARNING_PREFIXES = (
    "browser_state_final_publication_hash_not_available",
    "same_beam_state_fingerprint_only_partially_browser_exposed",
    "selected_family_not_exposed_in_browser_state",
    "expected_action_visual_state_not_observed",
    "expected_pass_visual_state_not_observed",
    "expected_action_or_pass_visual_state_not_observed",
    "expected_action_pass_or_blocked_visual_state_not_observed",
    "design_guide_section_parser_missed_final_card",
)


DEFAULT_REPRESENTATIVE_RECIPES = [
    {
        "scenario_id": "bending_fail_action",
        "recipe": "R1A_M300_V0",
        "expected_family_class": "repair_failure",
        "expected_visual_state": "action",
    },
    {
        "scenario_id": "shear_fail_action",
        "recipe": "R2A_M0_V400",
        "expected_family_class": "repair_failure",
        "expected_visual_state": "action",
    },
    {
        "scenario_id": "combined_fail_action",
        "recipe": "R3A_M300_V400",
        "expected_family_class": "combined_repair_failure",
        "expected_visual_state": "action",
    },
    {
        "scenario_id": "bending_overdesign_or_pass",
        "recipe": "R4A_M45_V0",
        "expected_family_class": "optimisation_or_terminal",
        "expected_visual_state": "action_or_pass",
    },
    {
        "scenario_id": "shear_overdesign_or_pass",
        "recipe": "R5A_M0_V150",
        "expected_family_class": "optimisation_or_terminal",
        "expected_visual_state": "action_or_pass",
    },
    {
        "scenario_id": "combined_overdesign_or_pass",
        "recipe": "R6A_M45_V150",
        "expected_family_class": "combined_optimisation_or_terminal",
        "expected_visual_state": "action_or_pass",
    },
    {
        "scenario_id": "terminal_pass",
        "recipe": "TERMINAL_EFFICIENT_NO_CLEANUP_SNAPSHOT",
        "expected_family_class": "terminal_pass",
        "expected_visual_state": "pass",
    },
    {
        "scenario_id": "local_cleanup_or_blocker",
        "recipe": "BENDING_LOW_SHEAR_IN_TARGET_LOCAL_CLEANUP_SNAPSHOT",
        "expected_family_class": "cleanup_or_blocker",
        "expected_visual_state": "action_or_pass_or_blocked",
    },
]


def _known_recipe_names() -> set[str]:
    names = {str(row.get("name")) for row in REGRESSION_CASES if row.get("name")}
    for row in FROZEN_RECIPES:
        for subcase in row.get("subcases") or []:
            if subcase.get("name"):
                names.add(str(subcase.get("name")))
    for row in DEBUG_CASES:
        if row.get("name"):
            names.add(str(row.get("name")))
    return names


def _selected_family_from_state(state: dict[str, Any]) -> str:
    if not state.get("available"):
        return ""
    final_payload = dict(state.get("final_publication_verifier_payload") or {})
    display_payload = dict(final_payload.get("display") or {})
    display_details = dict(display_payload.get("details") or {})
    primary_contract = dict(state.get("primary_button_contract") or {})
    card_attrs = dict(state.get("card_data_attributes") or {})
    debug_source_values = [
        dict(value)
        for value in dict(state.get("browser_debug_sources") or {}).values()
        if isinstance(value, dict)
    ]
    nested_debug_source_values = []
    for value in debug_source_values:
        for key in (
            "candidate_search_evidence",
            "selection_evidence",
            "display_truth",
            "button_contract",
        ):
            nested = value.get(key)
            if isinstance(nested, dict):
                nested_debug_source_values.append(dict(nested))
    for source in (
        final_payload,
        dict(final_payload.get("evidence") or {}),
        display_payload,
        display_details,
        dict(display_details.get("candidate_search_evidence") or {}),
        dict(display_details.get("target_band_evidence") or {}),
        primary_contract,
        card_attrs,
        dict(state.get("browser_shared_probe") or {}),
        *debug_source_values,
        *nested_debug_source_values,
    ):
        for key in (
            "selected_family_id",
            "selected_family",
            "published_family_id",
            "family",
            "cta_family_id",
            "apply_payload_family_id",
        ):
            value = str(source.get(key) or "").strip()
            if value:
                return value
    return ""


def _recipe_probe(scenario: dict[str, Any]) -> dict[str, Any]:
    state = dict(scenario.get("browser_state") or {})
    return {
        "browser_state_available": bool(state.get("available")),
        "requested_recipe": scenario.get("recipe"),
        "applied_recipe": (
            dict(state.get("browser_shared_probe") or {}).get("browser_recipe")
            or dict(state.get("summary_state_probe") or {}).get("browser_recipe")
        ),
        "browser_recipe_error": (
            dict(state.get("browser_shared_probe") or {}).get("browser_recipe_error")
            or dict(state.get("summary_state_probe") or {}).get("browser_recipe_error")
        ),
        "selected_family_id": _selected_family_from_state(state),
        "publication_hashes": dict(state.get("final_publication_hashes") or {}),
    }


def _final_card_probe_from_text(text: str) -> dict[str, Any]:
    text_value = str(text or "")
    final_markers = [marker for marker in FINAL_CARD_MARKERS if marker in text_value]
    loading_markers = [marker for marker in LOADING_SHELL_MARKERS if marker in text_value]
    status_markers = [
        marker
        for marker in ("PASS", "ACTION", "RECOMMEND", "BLOCKED", "ERROR", "PROOF_PENDING", "NEXT", "INFO")
        if marker in text_value
    ]
    return {
        "final_card_ready": bool(final_markers or status_markers),
        "final_markers": final_markers,
        "loading_markers": loading_markers,
        "status_markers": status_markers,
        "loading_shell_visible": bool(loading_markers),
        "loading_shell_only": bool(loading_markers and not final_markers and not status_markers),
        "text_hash": _stable_hash(text_value) if text_value else None,
        "text_sample": text_value[:700],
    }


def _wait_for_final_design_guide_card(page, *, timeout_s: float) -> dict[str, Any]:
    deadline = time.monotonic() + max(5.0, float(timeout_s))
    last_probe: dict[str, Any] = {}
    while time.monotonic() < deadline:
        try:
            body_text = str(page.locator("body").inner_text(timeout=2_000) or "")
            text = _design_guide_section(body_text)
            if not text:
                text = body_text
        except Exception as exc:
            last_probe = {
                "final_card_ready": False,
                "loading_shell_only": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
            time.sleep(0.5)
            continue
        last_probe = _final_card_probe_from_text(text)
        if last_probe.get("final_card_ready") and not last_probe.get("loading_shell_visible"):
            last_probe["wait_elapsed_sec"] = round(max(0.0, float(timeout_s) - (deadline - time.monotonic())), 3)
            return last_probe
        time.sleep(0.75)
    last_probe["wait_elapsed_sec"] = float(timeout_s)
    return last_probe


def _classify_scenario(row: dict[str, Any]) -> dict[str, Any]:
    checks = dict((row.get("checks") or {}))
    hard_failures = list(checks.get("hard_failures") or [])
    raw_warnings = list(checks.get("warnings") or [])
    warnings: list[str] = []
    non_visual_observations: list[str] = []
    for warning in raw_warnings:
        warning_text = str(warning)
        if any(warning_text.startswith(prefix) for prefix in NON_VISUAL_WARNING_PREFIXES):
            non_visual_observations.append(warning_text)
        else:
            warnings.append(warning_text)
    final_card_probe = dict(row.get("final_card_wait_probe") or {})
    if not final_card_probe.get("final_card_ready"):
        hard_failures.append("final_design_guide_card_not_ready")
    if final_card_probe.get("loading_shell_only"):
        hard_failures.append("final_design_guide_loading_shell_only")
    elif final_card_probe.get("loading_shell_visible"):
        hard_failures.append("final_design_guide_pending_shell_visible_with_final_card")
    if final_card_probe.get("final_card_ready") and "design_guide_section_not_found" in hard_failures:
        hard_failures = [item for item in hard_failures if item != "design_guide_section_not_found"]
        non_visual_observations.append("design_guide_section_parser_missed_final_card")
    recipe_probe = _recipe_probe(row)
    row["recipe_probe"] = recipe_probe
    if recipe_probe.get("browser_recipe_error"):
        hard_failures.append(f"browser_recipe_error:{recipe_probe.get('browser_recipe_error')}")
    selected_family = str(recipe_probe.get("selected_family_id") or "")
    if not selected_family:
        non_visual_observations.append("selected_family_not_exposed_in_browser_state")
    statuses = {str(value).upper() for value in checks.get("design_guide_statuses") or []}
    action_statuses = {"ACTION", "NEXT", "RECOMMEND"}
    pass_statuses = {"PASS"}
    expected_visual = str(row.get("expected_visual_state") or "")
    if expected_visual == "action" and not (statuses & action_statuses):
        non_visual_observations.append("expected_action_visual_state_not_observed")
    elif expected_visual == "pass" and not (statuses & pass_statuses):
        non_visual_observations.append("expected_pass_visual_state_not_observed")
    elif expected_visual == "action_or_pass" and not (statuses & {*action_statuses, *pass_statuses}):
        non_visual_observations.append("expected_action_or_pass_visual_state_not_observed")
    elif expected_visual == "action_or_pass_or_blocked" and not (
        statuses & {*action_statuses, "BLOCKED", *pass_statuses}
    ):
        non_visual_observations.append("expected_action_pass_or_blocked_visual_state_not_observed")
    return {
        "hard_failures": hard_failures,
        "warnings": warnings,
        "non_visual_observations": sorted(set(non_visual_observations)),
        "selected_family_id": selected_family,
        "observed_statuses": sorted(statuses),
        "recipe_probe": recipe_probe,
    }


def _capture_family_scenarios(
    *,
    base_url: str,
    recipes: list[dict[str, str]],
    headed: bool,
    timeout_s: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        try:
            for spec in recipes:
                context = browser.new_context(viewport={"width": 1600, "height": 1100})
                page = context.new_page()
                page.set_default_timeout(30_000)
                recipe = str(spec["recipe"])
                scenario_id = str(spec["scenario_id"])
                page.goto(
                    _query(base_url, {"page": "inputs", "browser_recipe": recipe}),
                    wait_until="domcontentloaded",
                    timeout=90_000,
                )
                try:
                    page.get_by_text("Inputs", exact=True).first.wait_for(
                        state="visible",
                        timeout=min(30_000, int(timeout_s * 1000)),
                    )
                except PlaywrightTimeoutError:
                    pass
                final_card_probe = _wait_for_final_design_guide_card(page, timeout_s=timeout_s)
                screenshot_path = ARTIFACT_DIR / (
                    f"design_guide_family_browser_live_visual_consistency_{scenario_id}_{_datetime_stamp()}.png"
                )
                row = _capture_visual_snapshot(page, scenario_id=scenario_id, screenshot_path=screenshot_path)
                row.update(
                    {
                        "recipe": recipe,
                        "expected_family_class": spec.get("expected_family_class"),
                        "expected_visual_state": spec.get("expected_visual_state"),
                        "final_card_wait_probe": final_card_probe,
                    }
                )
                row["classification"] = _classify_scenario(row)
                rows.append(row)
                context.close()
        finally:
            browser.close()
    return rows


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide Family Browser/Live Visual Consistency Snapshot",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Recipes sampled: `{len(payload.get('scenarios') or [])}`",
        f"- Hard failures: `{len(payload.get('hard_failures') or [])}`",
        f"- Warnings: `{len(payload.get('warnings') or [])}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        "",
        "## Scenario Rows",
        "",
        "| Scenario | Recipe | Final card | Selected family | Statuses | Hard failures | Visual warnings | Non-visual observations |",
        "|---|---|---|---|---|---:|---:|---:|",
    ]
    for row in payload.get("scenarios") or []:
        cls = dict(row.get("classification") or {})
        final_card = dict(row.get("final_card_wait_probe") or {})
        lines.append(
            "| `{scenario}` | `{recipe}` | `{final_card}` | `{family}` | `{statuses}` | `{failures}` | `{warnings}` | `{observations}` |".format(
                scenario=row.get("scenario_id"),
                recipe=row.get("recipe"),
                final_card=bool(final_card.get("final_card_ready")),
                family=cls.get("selected_family_id") or "",
                statuses=", ".join(cls.get("observed_statuses") or []),
                failures=len(cls.get("hard_failures") or []),
                warnings=len(cls.get("warnings") or []),
                observations=len(cls.get("non_visual_observations") or []),
            )
        )
    lines.extend(["", "## Hard Failures", ""])
    lines.extend([f"- `{failure}`" for failure in payload.get("hard_failures") or []] or ["- None"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- `{warning}`" for warning in payload.get("warnings") or []] or ["- None"])
    lines.extend(["", "## Supporting Artifacts", ""])
    for name, artifact in (payload.get("supporting_artifacts") or {}).items():
        lines.append(f"- `{name}`: found `{artifact.get('found')}`, status `{artifact.get('status')}`")
    lines.extend(["", "## Recommendation", "", payload.get("recommendation") or "No recommendation recorded.", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8529)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_FAMILY_VISUAL_BASE_URL"))
    parser.add_argument("--recipe", action="append", help="Recipe to sample; may be repeated.")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--timeout-s", type=float, default=60.0)
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _datetime_stamp()
    known = _known_recipe_names()
    if args.recipe:
        recipes = [
            {
                "scenario_id": str(recipe),
                "recipe": str(recipe),
                "expected_family_class": "user_requested",
                "expected_visual_state": "any",
            }
            for recipe in args.recipe
            if str(recipe).strip()
        ]
    else:
        recipes = list(DEFAULT_REPRESENTATIVE_RECIPES)
    unknown_recipes = [row["recipe"] for row in recipes if row["recipe"] not in known]

    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    process: subprocess.Popen | None = None
    errors: list[str] = []
    scenarios: list[dict[str, Any]] = []
    browser_live_mode = "started_streamlit"
    try:
        if args.base_url:
            browser_live_mode = "attached_to_existing_streamlit"
            _wait_for_http(base_url)
        else:
            before = dict(os.environ)
            os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
            try:
                process = _start_streamlit(args.port)
            finally:
                os.environ.clear()
                os.environ.update(before)
        scenarios = _capture_family_scenarios(
            base_url=base_url,
            recipes=recipes,
            headed=bool(args.headed),
            timeout_s=float(args.timeout_s),
        )
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()

    hard_failures: list[str] = []
    warnings: list[str] = []
    for row in scenarios:
        cls = dict(row.get("classification") or {})
        for failure in cls.get("hard_failures") or []:
            hard_failures.append(f"{row.get('scenario_id')}:{failure}")
        for warning in cls.get("warnings") or []:
            warnings.append(f"{row.get('scenario_id')}:{warning}")
    non_visual_observations = []
    for row in scenarios:
        cls = dict(row.get("classification") or {})
        for observation in cls.get("non_visual_observations") or []:
            non_visual_observations.append(f"{row.get('scenario_id')}:{observation}")
    for recipe in unknown_recipes:
        hard_failures.append(f"unknown_recipe:{recipe}")
    for error in errors:
        hard_failures.append(f"capture_error:{error}")

    supporting_artifacts = {
        "design_guide_family_render_model_formatting_snapshot": _latest_artifact(
            "design_guide_family_render_model_formatting_snapshot"
        ),
        "design_guide_family_formatting_uniformity_audit": _latest_artifact(
            "design_guide_family_formatting_uniformity_audit"
        ),
        "design_guide_independence_lock": _latest_artifact("design_guide_independence_lock"),
        "design_guide_render_bridge_lock": _latest_artifact("design_guide_render_bridge_lock"),
        "design_guide_compute_resolver_publication_bridge_lock": _latest_artifact(
            "design_guide_compute_resolver_publication_bridge_lock"
        ),
    }
    status = "FAIL" if not scenarios or hard_failures else ("PARTIAL" if warnings else "PASS")
    recommendation = (
        "No hard browser/live visual consistency failures were found across representative family scenarios."
        if status == "PASS"
        else "Fix the recorded hard browser/live visual consistency failures before treating family formatting as live-complete."
    )
    payload = {
        "schema": "design_guide_family_browser_live_visual_consistency_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "browser_live_mode": browser_live_mode,
        "base_url": base_url,
        "recipes_requested": recipes,
        "unknown_recipes": unknown_recipes,
        "scenarios": scenarios,
        "hard_failures": hard_failures,
        "warnings": warnings,
        "non_visual_observations": non_visual_observations,
        "supporting_artifacts": supporting_artifacts,
        "errors": errors,
        "recommendation": recommendation,
        "product_behaviour_changed": False,
        "family_runtimes_changed": False,
        "contracts_changed": False,
        "cta_routing_changed": False,
        "apply_routing_changed": False,
        "visible_wording_changed": False,
        "snapshot_hash": _stable_hash(
            {
                "status": status,
                "scenario_hashes": [row.get("scenario_hash") for row in scenarios],
                "hard_failures": hard_failures,
                "warnings": warnings,
            }
        ),
    }
    json_path = ARTIFACT_DIR / f"design_guide_family_browser_live_visual_consistency_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_family_browser_live_visual_consistency_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_family_browser_live_visual_consistency_snapshot {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print("hard_failures=" + json.dumps(hard_failures))
    print("warnings=" + json.dumps(warnings[:40]))
    return 0 if status in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
