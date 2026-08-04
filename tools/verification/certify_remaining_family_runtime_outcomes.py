"""Certify remaining Design Brain families through live browser runtime tuples.

Verifier-only. Starts an isolated browser-test Streamlit server unless a base
URL is supplied. It does not change production engineering logic.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
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

from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    TRACER_PATH,
    _browser_state_raw_candidates,
    _load_browser_state,
    _query,
    _start_streamlit,
    _wait_for_http,
    _wait_for_run_end,
)
from tools.verification.recipes.one_click_recipe_defs import find_named_case  # noqa: E402
from tools.verification.runtime_outcome_coverage_investigation import (  # noqa: E402
    _capture_page_payload,
    _investigation_registry,
    _lock_results_for_tuple,
    _run_mutation_sensitivity,
    _stable_hash,
    _tuple_from_capture,
)


AUDIT_DIR = ROOT / "artifacts" / "audits"
RUNTIME_RECIPE_DIR = ROOT / "artifacts" / "runtime_recipes"
RUNTIME_TUPLE_DIR = ROOT / "artifacts" / "runtime_tuples"
SCREENSHOT_DIR = ROOT / "artifacts" / "runtime_screenshots"


_FAMILY_TRACE_KEYS = {
    "overview_family_chooser_restamp",
    "selected_family_id",
    "published_family_id",
    "cta_family_id",
    "apply_payload_family_id",
    "family_selection_source",
    "family_route_owner",
    "matched_family_ids",
    "raw_state_flags",
    "selection_evidence",
    "governing_family",
    "publication_selected_family_id",
    "publication_verifier_selected_family_id",
    "reuse_decision",
}


def _family_stage_trace(value: Any, *, path: str = "state", depth: int = 0) -> list[dict[str, Any]]:
    """Collect family-identity checkpoints without persisting the full browser state."""
    if depth > 8:
        return []
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        captured = {
            str(key): item
            for key, item in value.items()
            if str(key) in _FAMILY_TRACE_KEYS
        }
        if captured:
            rows.append({"path": path, "values": captured})
        for key, item in value.items():
            if isinstance(item, (dict, list, tuple)):
                rows.extend(_family_stage_trace(item, path=f"{path}.{key}", depth=depth + 1))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            if isinstance(item, (dict, list, tuple)):
                rows.extend(_family_stage_trace(item, path=f"{path}[{index}]", depth=depth + 1))
    return rows


FAMILY_SPECS: tuple[dict[str, Any], ...] = (
    {
        "family": "SHEAR_FAIL_GOVERNS",
        "scenario": "shear_fail_action",
        "recipe": "LIVE_FUZZ_SHEAR_FAIL_GOVERNS_01",
        "expected_outcome": "ACTION",
        "expected_cta": "ENABLED",
        "expected_apply": "ENABLED",
        "post_apply_required": True,
    },
    {
        "family": "COMBINED_BENDING_SHEAR_FAIL",
        "scenario": "combined_fail_blocked",
        "recipe": "LIVE_FUZZ_COMBINED_BENDING_SHEAR_FAIL_GOVERNS_01",
        "expected_outcome": "BLOCKED",
        "expected_cta": "ABSENT",
        "expected_apply": "ABSENT",
        "accepted_families": ("COMBINED_BENDING_SHEAR_FAIL", "COMBINED_BENDING_SHEAR_FAIL_GOVERNS"),
    },
    {
        "family": "BENDING_OVERDESIGN_GOVERNS",
        "scenario": "bending_overdesign_action",
        "recipe": "LIVE_FUZZ_BENDING_OVERDESIGN_GOVERNS_02",
        "expected_outcome": "ACTION",
        "expected_cta": "ENABLED",
        "expected_apply": "ENABLED",
        "post_apply_required": True,
        "accepted_post_apply_families": (
            "BENDING_OVERDESIGN_GOVERNS",
            "COMBINED_OVERDESIGN",
        ),
    },
    {
        "family": "SHEAR_OVERDESIGN_GOVERNS",
        "scenario": "shear_overdesign_action",
        "recipe": "LIVE_FUZZ_SHEAR_OVERDESIGN_GOVERNS_01",
        "expected_outcome": "ACTION",
        "expected_cta": "ENABLED",
        "expected_apply": "ENABLED",
        "post_apply_required": True,
    },
    {
        "family": "COMBINED_OVERDESIGN",
        "scenario": "combined_overdesign_action",
        "recipe": "LIVE_FUZZ_COMBINED_OVERDESIGN_GOVERNS_01",
        "expected_outcome": "ACTION",
        "expected_cta": "ENABLED",
        "expected_apply": "ENABLED",
        "post_apply_required": True,
        "accepted_families": ("COMBINED_OVERDESIGN", "COMBINED_OVERDESIGN_GOVERNS"),
    },
    {
        "family": "MIN_BENDING_REO_GOVERNS",
        "scenario": "min_bending_reo_direct_runtime",
        "recipe": "",
        "expected_outcome": "BLOCKED",
        "expected_cta": "ABSENT",
        "expected_apply": "ABSENT",
        "compatibility_owner_family": "BENDING_OVERDESIGN_GOVERNS",
        "compliance_script": "tools/verification/design_brain_family_contract_compliance_min_bending_reo.py",
        "known_gap": "Current terminal acceptance tooling treats this as compatibility-owned by BENDING_OVERDESIGN_GOVERNS, not a direct browser-selected family.",
    },
    {
        "family": "MIN_SHEAR_REO_GOVERNS",
        "scenario": "min_shear_reo_direct_runtime",
        "recipe": "",
        "expected_outcome": "BLOCKED",
        "expected_cta": "ABSENT",
        "expected_apply": "ABSENT",
        "compatibility_owner_family": "SHEAR_OVERDESIGN_GOVERNS",
        "compliance_script": "tools/verification/design_brain_family_contract_compliance_min_shear_reo.py",
        "known_gap": "Current terminal acceptance tooling treats this as compatibility-owned by SHEAR_OVERDESIGN_GOVERNS, not a direct browser-selected family.",
    },
    {
        "family": "GEOMETRY_DETAILING_GOVERNS",
        "scenario": "geometry_detailing_action",
        "recipe": "PRODUCT_INVALID_LONGITUDINAL_REO_SPACING_NO_ACTIONS",
        "expected_outcome": "ACTION",
        "expected_cta": "ENABLED",
        "expected_apply": "ENABLED",
        "post_apply_required": True,
    },
    {
        "family": "SERVICEABILITY_GOVERNS",
        "scenario": "serviceability_terminal_or_blocked",
        "recipe": "LIVE_FUZZ_SERVICEABILITY_GOVERNS_01",
        "expected_outcome": "BLOCKED",
        "expected_cta": "ABSENT",
        "expected_apply": "ABSENT",
        "allow_terminal_outcomes": ("BLOCKED", "PASS", "PROOF_PENDING", "ERROR"),
    },
    {
        "family": "LOCKED_NO_REPAIR",
        "scenario": "locked_no_repair_blocked",
        "recipe": "PRODUCT_LOCKED_NO_REPAIR_SHEAR_FAIL",
        "expected_outcome": "BLOCKED",
        "expected_cta": "ABSENT",
        "expected_apply": "ABSENT",
    },
    {
        "family": "TARGET_BAND_REACHED",
        "scenario": "target_band_pass",
        "recipe": "TERMINAL_EFFICIENT_NO_CLEANUP_SNAPSHOT",
        "expected_outcome": "PASS",
        "expected_cta": "ABSENT",
        "expected_apply": "ABSENT",
    },
    {
        "family": "EXACT_STOP_PROVEN",
        "scenario": "exact_stop_pass",
        "recipe": "TERMINAL_EXACT_STOP_PROVEN_SNAPSHOT",
        "expected_outcome": "PASS",
        "expected_cta": "ABSENT",
        "expected_apply": "ABSENT",
    },
    {
        "family": "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        "scenario": "bending_fail_shear_overdesign_owner_runtime",
        "recipe": "LIVE_FUZZ_BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS_01",
        "expected_outcome": "ACTION",
        "expected_cta": "ENABLED",
        "expected_apply": "ENABLED",
        "post_apply_required": True,
        "accepted_families": ("BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",),
        "accepted_post_apply_families": ("TARGET_BAND_REACHED",),
        "compliance_script": "tools/verification/families/bending_fail_shear_overdesign_governs_lock_verifier.py",
    },
    {
        "family": "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        "scenario": "shear_fail_bending_overdesign_owner_runtime",
        "recipe": "LIVE_FUZZ_SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS_01",
        "expected_outcome": "ACTION",
        "expected_cta": "ENABLED",
        "expected_apply": "ENABLED",
        "post_apply_required": True,
        "accepted_families": (
            "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        ),
        "accepted_post_apply_families": ("TARGET_BAND_REACHED",),
        "compliance_script": "tools/verification/families/shear_fail_bending_overdesign_governs_lock_verifier.py",
    },
)


def _stamp() -> str:
    return datetime.now().replace(microsecond=0).isoformat().replace(":", "-")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _recipe_artifact(spec: dict[str, Any], stamp: str) -> dict[str, Any]:
    recipe_name = str(spec.get("recipe") or "")
    named = find_named_case(recipe_name) if recipe_name else None
    return {
        "schema": "design_brain_runtime_family_recipe.v1",
        "created_at": stamp,
        "family": spec["family"],
        "scenario": spec["scenario"],
        "browser_recipe": recipe_name,
        "recipe_exists": bool(named),
        "recipe_kind": named.get("kind") if isinstance(named, dict) else "",
        "engineering_inputs": dict(named.get("changes") or {}) if isinstance(named, dict) else {},
        "expected_governing_family": spec["family"],
        "accepted_families": list(spec.get("accepted_families") or (spec["family"],)),
        "accepted_post_apply_families": list(
            spec.get("accepted_post_apply_families") or spec.get("accepted_families") or (spec["family"],)
        ),
        "expected_outcome": spec.get("expected_outcome"),
        "expected_cta_state": spec.get("expected_cta"),
        "expected_apply_state": spec.get("expected_apply"),
        "expected_family_contract": "runtime_card_data_attribute_family_contract",
        "expected_publication_builder": "FinalDesignGuidePublication",
        "expected_display_builder": "FinalDesignGuideDisplay",
        "known_gap": spec.get("known_gap", ""),
    }


def _visible_action_buttons(page) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    locator = page.get_by_role("button")
    try:
        count = min(locator.count(), 80)
    except Exception:
        count = 0
    for index in range(count):
        button = locator.nth(index)
        try:
            text = " ".join(str(button.inner_text(timeout=500) or "").split())
        except Exception:
            text = ""
        if "Apply" not in text and "Run one-click" not in text:
            continue
        try:
            enabled = bool(button.is_enabled())
        except Exception:
            enabled = False
        rows.append({"index": index, "text": text, "enabled": enabled})
    return rows


def _click_first_action(page) -> dict[str, Any]:
    locator = page.get_by_role("button")
    try:
        count = min(locator.count(), 80)
    except Exception:
        count = 0
    for index in range(count):
        button = locator.nth(index)
        try:
            text = " ".join(str(button.inner_text(timeout=500) or "").split())
            enabled = bool(button.is_enabled())
        except Exception:
            continue
        if enabled and ("Apply" in text or "Run one-click" in text):
            button.click(timeout=10_000)
            return {"clicked": True, "index": index, "text": text}
    return {"clicked": False, "reason": "no_enabled_apply_or_one_click_button"}


def _load_latest_browser_state(page, *, fallback_timeout_ms: int = 5_000) -> dict[str, Any]:
    """Prefer the richest current post-render probe over stale retained DOM probes."""

    candidates: list[tuple[dict[str, Any], int]] = []
    for dom_index, raw in enumerate(_browser_state_raw_candidates(page)):
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        if isinstance(payload, dict):
            candidates.append((payload, dom_index))
    if not candidates:
        return _load_browser_state(page, fallback_timeout_ms=fallback_timeout_ms)

    post_render = [
        candidate
        for candidate in candidates
        if str(candidate[0].get("browser_probe_phase") or "").strip()
        == "post_page_render"
    ]
    pool = post_render or candidates

    def _rank(candidate: tuple[dict[str, Any], int]) -> tuple[int, int, int]:
        payload, dom_index = candidate
        browser_debug = dict(payload.get("browser_debug_probe") or {})
        typed_apply_seen = bool(browser_debug.get("typed_inputs_apply_probe"))
        try:
            results_version = int(payload.get("results_version") or 0)
        except (TypeError, ValueError):
            results_version = 0
        return (int(typed_apply_seen), results_version, dom_index)

    return max(pool, key=_rank)[0]


def _browser_state_candidate_summaries(page) -> list[dict[str, Any]]:
    """Expose state-selection evidence without changing the selection policy."""

    summaries: list[dict[str, Any]] = []
    for dom_index, raw in enumerate(_browser_state_raw_candidates(page)):
        try:
            payload = json.loads(raw)
        except Exception as exc:
            summaries.append(
                {
                    "dom_index": dom_index,
                    "json_error": f"{type(exc).__name__}: {exc}",
                    "raw_length": len(raw),
                }
            )
            continue
        if not isinstance(payload, dict):
            continue
        browser_debug = dict(payload.get("browser_debug_probe") or {})
        typed_apply = dict(browser_debug.get("typed_inputs_apply_probe") or {})
        summaries.append(
            {
                "dom_index": dom_index,
                "raw_length": len(raw),
                "browser_probe_phase": payload.get("browser_probe_phase"),
                "results_version": payload.get("results_version"),
                "browser_shared_b": dict(payload.get("browser_shared_probe") or {}).get("b"),
                "summary_b": dict(payload.get("summary_state_probe") or {}).get("b"),
                "active_b": dict(payload.get("active_beam_record_probe") or {}).get("b"),
                "typed_apply_status": typed_apply.get("status"),
                "typed_apply_updates": dict(typed_apply.get("updates") or {}),
                "browser_recipe_last_action": dict(
                    browser_debug.get("browser_recipe_last_action") or {}
                ).get("action"),
            }
        )
    return summaries


def _capture_tuple_now(page, *, scenario_id: str, recipe: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    payload = _capture_page_payload(page)
    state = _load_latest_browser_state(page, fallback_timeout_ms=5_000)
    tuple_row = _tuple_from_capture(scenario_id=scenario_id, recipe_id=recipe, payload=payload, state=state)
    tuple_row["family_stage_trace"] = _family_stage_trace(state)
    tuple_row["typed_apply_cutover_enabled"] = bool(
        (state.get("browser_debug_probe") or {}).get("typed_apply_cutover_enabled")
    )
    browser_debug = dict(state.get("browser_debug_probe") or {})
    tuple_row["typed_apply_probe"] = {
        "cutover_enabled": bool(browser_debug.get("typed_apply_cutover_enabled")),
        "recipe_seed_token_count": browser_debug.get(
            "browser_recipe_global_seed_token_count"
        ),
        "accepted_fingerprint_count": browser_debug.get(
            "post_cleanup_accepted_fingerprint_count"
        ),
        "accepted_fingerprint_audit": dict(
            browser_debug.get("post_cleanup_accepted_fingerprint_audit") or {}
        ),
        **dict(browser_debug.get("typed_inputs_apply_probe") or {}),
    }
    tuple_row["post_cleanup_acceptance_probe"] = dict(
        state.get("post_cleanup_acceptance_probe") or {}
    )
    tuple_row["family_exact_stop_acceptance_probe"] = dict(
        dict(state.get("guidance_compute_probe") or {}).get(
            "family_exact_stop_acceptance_probe"
        )
        or {}
    )
    tuple_row["family_ladder_runtime_result"] = dict(
        dict(state.get("guidance_compute_probe") or {}).get(
            "family_ladder_runtime_result"
        )
        or {}
    )
    design_guide_debug = dict(
        (state.get("design_guide_probe") or {}).get("debug_bundle") or {}
    )
    tuple_row["family_ladder_candidate_trace"] = list(
        dict(state.get("guidance_compute_probe") or {}).get(
            "family_ladder_candidate_trace"
        )
        or design_guide_debug.get("family_ladder_candidate_trace")
        or []
    )
    publication_candidate_search = dict(
        dict(
            dict(state.get("final_publication_verifier_payload") or {}).get(
                "evidence"
            )
            or {}
        ).get("candidate_search_evidence")
        or {}
    )
    design_guide_candidate_search = dict(
        dict(
            dict(state.get("design_guide_probe") or {}).get("debug_bundle")
            or {}
        ).get("candidate_search_evidence")
        or {}
    )
    tuple_row["candidate_search_evidence"] = (
        publication_candidate_search or design_guide_candidate_search
    )
    tuple_row["browser_recipe_applied_state"] = dict(
        state.get("browser_recipe_applied_state") or {}
    )
    tuple_row["engineering_snapshot_probe"] = dict(
        state.get("engineering_snapshot_probe") or {}
    )
    tuple_row["summary_state_probe"] = dict(
        state.get("summary_state_probe") or {}
    )
    tuple_row["summary_overview_probe"] = dict(
        state.get("summary_overview_probe") or {}
    )
    tuple_row["active_beam_record_probe"] = dict(
        state.get("active_beam_record_probe") or {}
    )
    tuple_row["typed_post_apply_rehydrate_probe"] = dict(
        browser_debug.get("typed_post_apply_rehydrate_probe") or {}
    )
    tuple_row["browser_recipe_last_action"] = dict(
        browser_debug.get("browser_recipe_last_action") or {}
    )
    tuple_row["browser_probe_phase"] = state.get("browser_probe_phase")
    tuple_row["results_version"] = state.get("results_version")
    tuple_row["browser_shared_probe"] = dict(state.get("browser_shared_probe") or {})
    tuple_row["browser_state_candidate_summaries"] = _browser_state_candidate_summaries(page)
    tuple_row["post_apply_decision_probe"] = {
        key: design_guide_debug.get(key)
        for key in (
            "guidance_branch",
            "target_band_with_eps_passed",
            "post_click_accepted_green",
            "post_click_accepted_green_valid",
            "post_click_accepted_green_invalid_reason",
            "post_click_families_below_final_threshold",
            "post_click_materially_overprovided_families",
            "post_click_exact_blockers_by_family",
            "terminal_state_blocked_by_local_cleanup",
            "terminal_state_blocked_reason",
        )
        if key in design_guide_debug
    }
    return tuple_row, payload, state


def _wait_for_post_apply_settled_tuple(
    page,
    *,
    scenario_id: str,
    recipe: str,
    timeout_s: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    deadline = time.time() + max(8.0, float(timeout_s))
    observations: list[dict[str, Any]] = []
    latest: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            tuple_row, _payload, _state = _capture_tuple_now(page, scenario_id=scenario_id, recipe=recipe)
        except Exception as exc:
            observations.append({"error": f"{type(exc).__name__}: {exc}"})
            page.wait_for_timeout(750)
            continue
        latest = dict(tuple_row)
        observation = {
            "outcome_code": tuple_row.get("outcome_code"),
            "family_code": tuple_row.get("family_code"),
            "cta_state": tuple_row.get("cta_state"),
            "apply_state": tuple_row.get("apply_state"),
            "publication_builder": tuple_row.get("publication_builder"),
            "display_builder": tuple_row.get("display_builder"),
            "publication_authority_hash_present": bool(tuple_row.get("publication_authority_hash")),
            "final_card_ready": bool((tuple_row.get("visible") or {}).get("final_card_ready")),
            "browser_probe_phase": tuple_row.get("browser_probe_phase"),
            "results_version": tuple_row.get("results_version"),
            "browser_shared_b": dict(tuple_row.get("browser_shared_probe") or {}).get("b"),
            "summary_b": dict(tuple_row.get("summary_state_probe") or {}).get("b"),
            "active_b": dict(tuple_row.get("active_beam_record_probe") or {}).get("b"),
            "typed_apply_status": dict(tuple_row.get("typed_apply_probe") or {}).get("status"),
        }
        observations.append(observation)
        if (
            tuple_row.get("outcome_code") == "PASS"
            and tuple_row.get("cta_state") == "ABSENT"
            and tuple_row.get("apply_state") == "ABSENT"
            and tuple_row.get("publication_builder") == "FinalDesignGuidePublication"
            and tuple_row.get("display_builder") == "FinalDesignGuideDisplay"
            and bool(tuple_row.get("publication_authority_hash"))
            and bool((tuple_row.get("visible") or {}).get("final_card_ready"))
        ):
            return tuple_row, observations
        page.wait_for_timeout(1_000)
    return latest, observations


def _expectation_failures(tuple_row: dict[str, Any], spec: dict[str, Any], state: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    family = str(tuple_row.get("family_code") or "")
    accepted = {str(item) for item in (spec.get("accepted_families") or (spec["family"],))}
    expected_outcomes = set(spec.get("allow_terminal_outcomes") or (spec.get("expected_outcome"),))
    expected_outcomes.discard(None)
    if family not in accepted:
        failures.append(f"expected_family_mismatch:expected={sorted(accepted)}:actual={family}")
    if expected_outcomes and str(tuple_row.get("outcome_code") or "") not in expected_outcomes:
        failures.append(
            f"expected_outcome_mismatch:expected={sorted(expected_outcomes)}:actual={tuple_row.get('outcome_code')}"
        )
    if spec.get("expected_cta") and tuple_row.get("cta_state") != spec.get("expected_cta"):
        failures.append(f"expected_cta_mismatch:expected={spec.get('expected_cta')}:actual={tuple_row.get('cta_state')}")
    if spec.get("expected_apply") and tuple_row.get("apply_state") != spec.get("expected_apply"):
        failures.append(
            f"expected_apply_mismatch:expected={spec.get('expected_apply')}:actual={tuple_row.get('apply_state')}"
        )
    applied_recipe = str(state.get("browser_recipe") or "")
    recipe_error = str(state.get("browser_recipe_error") or "")
    if spec.get("recipe") and applied_recipe != spec.get("recipe"):
        failures.append(f"requested_browser_recipe_mismatch:requested={spec.get('recipe')}:applied={applied_recipe}")
    if recipe_error:
        failures.append(f"browser_recipe_error:{recipe_error}")
    for lock in _lock_results_for_tuple(tuple_row, _investigation_registry()):
        if lock.get("status") == "FAIL":
            failures.append(f"tuple_lock:{lock.get('lock')}:{lock.get('failure')}")
    return failures


def _certify_one(
    *,
    page,
    base_url: str,
    spec: dict[str, Any],
    stamp: str,
    timeout_s: float,
    click_apply: bool,
    certified_families: set[str] | None = None,
) -> dict[str, Any]:
    family = str(spec["family"])
    scenario = str(spec["scenario"])
    recipe = str(spec.get("recipe") or "")
    row: dict[str, Any] = {
        "family": family,
        "scenario": scenario,
        "recipe": recipe,
        "status": "NOT_CERTIFIED",
        "failures": [],
        "artifacts": {},
    }
    recipe_payload = _recipe_artifact(spec, stamp)
    recipe_path = RUNTIME_RECIPE_DIR / f"{family}_{scenario}_{stamp}.json"
    _write_json(recipe_path, recipe_payload)
    row["artifacts"]["recipe"] = str(recipe_path.relative_to(ROOT))
    compatibility_owner = str(spec.get("compatibility_owner_family") or "").strip()
    compatibility_owner_via_recipe = bool(spec.get("compatibility_owner_via_recipe"))
    compliance_script = str(spec.get("compliance_script") or "").strip()
    if compatibility_owner:
        row["compatibility_owner_family"] = compatibility_owner
        row["compatibility_mode"] = "LIVE_OWNER_ROUTE" if compatibility_owner_via_recipe else "COMPATIBILITY_OWNER"
    if compatibility_owner and not compatibility_owner_via_recipe:
        certified_set = {str(item) for item in (certified_families or set())}
        row["compatibility_certified"] = False
        if compatibility_owner not in certified_set:
            row["failures"].append(f"compatibility_owner_not_certified:{compatibility_owner}")
            return row
        if not compliance_script:
            row["failures"].append("compatibility_compliance_script_missing")
            return row
        completed = subprocess.run(
            [sys.executable, compliance_script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=120,
        )
        row["compatibility_compliance"] = {
            "script": compliance_script,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr_tail": completed.stderr[-4000:],
        }
        if completed.returncode != 0:
            row["failures"].append(f"compatibility_compliance_failed:{compliance_script}")
            return row
        row["compatibility_certified"] = True
        row["status"] = "CERTIFIED"
        return row
    if spec.get("known_gap"):
        row["failures"].append(f"known_gap:{spec.get('known_gap')}")
        return row
    if not recipe_payload["recipe_exists"]:
        row["failures"].append(f"recipe_missing:{recipe}")
        return row

    target_url = _query(base_url, {"page": "inputs", "browser_recipe": recipe, "browser_test_mode": "1", "cid": scenario})
    page.goto(target_url, wait_until="domcontentloaded", timeout=90_000)
    try:
        page.get_by_label("Browser state").wait_for(state="attached", timeout=15_000)
    except PlaywrightTimeoutError:
        row["failures"].append("browser_state_probe_not_attached")
    try:
        page.wait_for_selector(
            "[data-testid='design-guide-card'], [data-outcome-state], [data-publication-hash], .fast-guidance-item",
            timeout=int(max(5.0, timeout_s) * 1000),
        )
    except PlaywrightTimeoutError:
        row["failures"].append("final_card_contract_not_attached")
    page.wait_for_timeout(1_000)

    screenshot_path = SCREENSHOT_DIR / f"{family}_{scenario}_before_{stamp}.png"
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(screenshot_path), full_page=True)
    row["artifacts"]["screenshot_before"] = str(screenshot_path.relative_to(ROOT))
    tuple_row, payload, state = _capture_tuple_now(
        page,
        scenario_id=scenario,
        recipe=recipe,
    )
    tuple_row["browser_recipe_probe"] = {
        "requested_browser_recipe": recipe,
        "applied_browser_recipe": state.get("browser_recipe"),
        "browser_recipe_kind": state.get("browser_recipe_kind"),
        "browser_recipe_error": state.get("browser_recipe_error"),
        "applied_state_hash": _stable_hash(state.get("browser_recipe_applied_state") or {}),
    }
    tuple_path = RUNTIME_TUPLE_DIR / f"runtime_tuple_{family}_{scenario}_{stamp}.json"
    _write_json(tuple_path, tuple_row)
    row["artifacts"]["runtime_tuple"] = str(tuple_path.relative_to(ROOT))
    row["tuple"] = tuple_row
    row["action_buttons"] = _visible_action_buttons(page)
    row["failures"].extend(_expectation_failures(tuple_row, spec, state))

    if not row["failures"] and spec.get("post_apply_required"):
        if not click_apply:
            row["failures"].append("post_apply_not_run:click_apply_disabled")
        else:
            tracer_offset = TRACER_PATH.stat().st_size if TRACER_PATH.exists() else 0
            before_hash = str(tuple_row.get("engineering_hash") or "")
            click = _click_first_action(page)
            row["apply_click"] = click
            if not click.get("clicked"):
                row["failures"].append(f"apply_click_failed:{click.get('reason')}")
            else:
                run_end, _ = _wait_for_run_end(tracer_offset, timeout_s=45.0, start_time_ms=None)
                post_tuple, post_wait_observations = _wait_for_post_apply_settled_tuple(
                    page,
                    scenario_id=f"{scenario}_post_apply",
                    recipe=recipe,
                    timeout_s=45.0,
                )
                post_path = RUNTIME_TUPLE_DIR / f"runtime_tuple_{family}_{scenario}_post_apply_{stamp}.json"
                _write_json(post_path, post_tuple)
                screenshot_after = SCREENSHOT_DIR / f"{family}_{scenario}_after_{stamp}.png"
                page.screenshot(path=str(screenshot_after), full_page=True)
                row["artifacts"]["runtime_tuple_post_apply"] = str(post_path.relative_to(ROOT))
                row["artifacts"]["screenshot_after"] = str(screenshot_after.relative_to(ROOT))
                row["post_apply"] = {
                    "run_end": run_end,
                    "post_tuple": post_tuple,
                    "settle_observations": post_wait_observations,
                    "engineering_hash_changed": bool(before_hash and before_hash != post_tuple.get("engineering_hash")),
                }
                typed_apply_probe = dict(post_tuple.get("typed_apply_probe") or {})
                typed_transaction_proven = bool(
                    typed_apply_probe.get("cutover_enabled")
                    and typed_apply_probe.get("status") == "rerun_required"
                    and dict(typed_apply_probe.get("updates") or {})
                    and before_hash
                    and before_hash != post_tuple.get("engineering_hash")
                    and post_tuple.get("outcome_code") == "PASS"
                    and post_tuple.get("cta_state") == "ABSENT"
                    and post_tuple.get("apply_state") == "ABSENT"
                )
                row["post_apply"]["typed_transaction_proven"] = typed_transaction_proven
                if not run_end and not typed_transaction_proven:
                    row["failures"].append("post_apply_single_transaction_not_proven")
                if before_hash and before_hash == post_tuple.get("engineering_hash"):
                    row["failures"].append("post_apply_engineering_hash_unchanged")
                if not (post_tuple.get("visible") or {}).get("final_card_ready"):
                    row["failures"].append("post_apply_final_card_not_ready")
                if not post_tuple.get("publication_authority_hash"):
                    row["failures"].append("post_apply_publication_authority_hash_missing")
                if post_tuple.get("publication_builder") != "FinalDesignGuidePublication":
                    row["failures"].append(
                        f"post_apply_publication_builder_not_proven:{post_tuple.get('publication_builder')}"
                    )
                if post_tuple.get("display_builder") != "FinalDesignGuideDisplay":
                    row["failures"].append(f"post_apply_display_builder_not_proven:{post_tuple.get('display_builder')}")
                if post_tuple.get("outcome_code") != "PASS":
                    row["failures"].append(f"post_apply_outcome_not_pass:{post_tuple.get('outcome_code')}")
                if post_tuple.get("cta_state") != "ABSENT":
                    row["failures"].append(f"post_apply_cta_not_absent:{post_tuple.get('cta_state')}")
                if post_tuple.get("apply_state") != "ABSENT":
                    row["failures"].append(f"post_apply_apply_not_absent:{post_tuple.get('apply_state')}")
                post_family = str(post_tuple.get("family_code") or "")
                accepted_post_families = {
                    str(item)
                    for item in (spec.get("accepted_post_apply_families") or spec.get("accepted_families") or (family,))
                }
                accepted_post_families.update({"GENERAL", "TARGET_BAND_REACHED"})
                if post_family and post_family not in accepted_post_families:
                    row["failures"].append(f"post_apply_family_changed_without_expected_contract:{post_family}")

    if compliance_script and compatibility_owner_via_recipe and not row["failures"]:
        completed = subprocess.run(
            [sys.executable, compliance_script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=120,
        )
        row["compatibility_compliance"] = {
            "script": compliance_script,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr_tail": completed.stderr[-4000:],
        }
        if completed.returncode != 0:
            row["failures"].append(f"compatibility_compliance_failed:{compliance_script}")
        else:
            row["compatibility_certified"] = True

    row["mutation_detection"] = _run_mutation_sensitivity([tuple_row], _investigation_registry())
    if row["mutation_detection"].get("status") != "PASS":
        row["failures"].append("mutation_detection_failed")
    row["status"] = "CERTIFIED" if not row["failures"] else "NOT_CERTIFIED"
    return row


def _table(rows: list[list[Any]]) -> str:
    lines = [
        "| Family | Runtime Seen | Outcome | Browser | CTA | Apply | Post Apply | Fallback | Compatibility | Certified |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append("|" + "|".join(str(cell).replace("|", "/") for cell in row) + "|")
    return "\n".join(lines)


def _write_reports(
    stamp: str,
    rows: list[dict[str, Any]],
    stopped_reason: str,
    selected_specs: tuple[dict[str, Any], ...] = FAMILY_SPECS,
) -> dict[str, str]:
    row_by_family = {str(row.get("family") or ""): row for row in rows}
    complete_rows: list[dict[str, Any]] = list(rows)
    for spec in selected_specs:
        family = str(spec["family"])
        if family in row_by_family:
            continue
        complete_rows.append(
            {
                "family": family,
                "scenario": spec["scenario"],
                "recipe": spec.get("recipe") or "",
                "status": "NOT_CERTIFIED",
                "failures": ["not_attempted_due_to_prior_stop_condition"],
                "artifacts": {},
            }
        )
    matrix_rows = []
    for row in complete_rows:
        tup = dict(row.get("tuple") or {})
        post = dict(row.get("post_apply") or {})
        compatibility_owner = str(row.get("compatibility_owner_family") or "")
        compatibility_certified = bool(row.get("compatibility_certified"))
        compatibility_mode = str(row.get("compatibility_mode") or "")
        compatibility_shell_certified = compatibility_certified and compatibility_mode == "COMPATIBILITY_OWNER"
        compatibility_cell = f"owner:{compatibility_owner}" if compatibility_owner else (
            tup.get("compatibility_path_used") if tup else ""
        )
        matrix_rows.append(
            [
                row.get("family"),
                "OWNER" if compatibility_shell_certified else bool(tup),
                "COMPATIBILITY_OWNER" if compatibility_shell_certified else (tup.get("outcome_code") or ""),
                "PASS"
                if compatibility_shell_certified or (tup.get("visible") or {}).get("final_card_ready")
                else "FAIL",
                "ABSENT" if compatibility_shell_certified else (tup.get("cta_state") or ""),
                "ABSENT" if compatibility_shell_certified else (tup.get("apply_state") or ""),
                "PASS"
                if post and not any("post_apply" in str(f) for f in row.get("failures") or [])
                else ("N/A" if not row.get("recipe") else "FAIL"),
                tup.get("fallback_path_used") if tup else "",
                f"{compatibility_cell} ({compatibility_mode})" if compatibility_cell and compatibility_mode else compatibility_cell,
                row.get("status"),
            ]
        )
    certified = [row for row in complete_rows if row.get("status") == "CERTIFIED"]
    uncertified = [row for row in complete_rows if row.get("status") != "CERTIFIED"]
    payload = {
        "status": "PASS" if len(certified) == len(selected_specs) else "FAIL",
        "generated_at": stamp,
        "stopped_reason": stopped_reason,
        "certified_count": len(certified),
        "required_count": len(selected_specs),
        "attempted_count": len(rows),
        "families": complete_rows,
    }
    json_path = AUDIT_DIR / f"remaining_family_runtime_certification_{stamp}.json"
    matrix_path = AUDIT_DIR / f"remaining_family_runtime_certification_matrix_{stamp}.md"
    scorecard_path = AUDIT_DIR / f"final_all_family_runtime_certification_scorecard_{stamp}.md"
    _write_json(json_path, payload)
    _write_text(
        matrix_path,
        "\n".join(
            [
                "# Remaining Family Runtime Certification Matrix",
                "",
                f"Status: `{payload['status']}`",
                "",
                _table(matrix_rows),
                "",
                "## Uncertified Families",
                "",
                "```json",
                json.dumps(
                    [
                        {"family": row.get("family"), "scenario": row.get("scenario"), "failures": row.get("failures")}
                        for row in uncertified
                    ],
                    indent=2,
                    sort_keys=True,
                    default=str,
                ),
                "```",
            ]
        ),
    )
    _write_text(
        scorecard_path,
        "\n".join(
            [
                "# Final All-Family Runtime Certification Scorecard",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"- Certified families: `{len(certified)}` of `{len(selected_specs)}`",
                f"- Runtime rows attempted: `{len(rows)}`",
                f"- Families not attempted after stop: `{len(selected_specs) - len(rows)}`",
                f"- Stop reason: `{stopped_reason or 'completed_attempts'}`",
                "",
                "The Design Brain is not fully certified unless every listed family is `CERTIFIED`.",
                "",
                "## Matrix",
                "",
                _table(matrix_rows),
            ]
        ),
    )
    return {
        "json": str(json_path),
        "matrix": str(matrix_path),
        "scorecard": str(scorecard_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="", help="Existing base URL. If omitted, starts isolated Streamlit.")
    parser.add_argument("--port", type=int, default=9329)
    parser.add_argument("--timeout-s", type=float, default=45.0)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--click-apply", action="store_true", help="Click Apply for ACTION rows.")
    parser.add_argument("--continue-after-fail", action="store_true", help="Diagnostic mode only; certification still fails.")
    parser.add_argument("--family", action="append", default=[], help="Limit certification to one or more family ids.")
    args = parser.parse_args(argv)

    stamp = _stamp()
    selected_specs = FAMILY_SPECS
    if args.family:
        requested = {str(item).strip().upper() for item in args.family if str(item).strip()}
        selected_specs = tuple(spec for spec in FAMILY_SPECS if str(spec["family"]).upper() in requested)
        missing = sorted(requested - {str(spec["family"]).upper() for spec in selected_specs})
        if missing:
            raise SystemExit(f"Unknown family filter(s): {', '.join(missing)}")
    process: subprocess.Popen | None = None
    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    rows: list[dict[str, Any]] = []
    stopped_reason = ""
    for spec in selected_specs:
        recipe_payload = _recipe_artifact(spec, stamp)
        recipe_path = RUNTIME_RECIPE_DIR / f"{spec['family']}_{spec['scenario']}_{stamp}.json"
        _write_json(recipe_path, recipe_payload)
    try:
        if args.base_url:
            _wait_for_http(base_url)
        else:
            process = _start_streamlit(args.port)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            try:
                page = browser.new_page(viewport={"width": 1600, "height": 1100})
                for spec in selected_specs:
                    print(f"[certify] {spec['family']} recipe={spec.get('recipe')}", flush=True)
                    row = _certify_one(
                        page=page,
                        base_url=base_url,
                        spec=spec,
                        stamp=stamp,
                        timeout_s=args.timeout_s,
                        click_apply=bool(args.click_apply),
                        certified_families={str(item.get("family") or "") for item in rows if item.get("status") == "CERTIFIED"},
                    )
                    rows.append(row)
                    if row.get("status") != "CERTIFIED" and not args.continue_after_fail:
                        stopped_reason = f"stop_condition:{row.get('family')}:{'; '.join(row.get('failures') or [])}"
                        break
            finally:
                browser.close()
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()
    paths = _write_reports(stamp, rows, stopped_reason, selected_specs=selected_specs)
    passed = all(row.get("status") == "CERTIFIED" for row in rows) and len(rows) == len(selected_specs)
    print(json.dumps({"status": "PASS" if passed else "FAIL", "paths": paths, "stopped_reason": stopped_reason}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
