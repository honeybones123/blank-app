"""Deterministic structural gate for the per-family 10-fuzz audit.

The requested full live audit is intentionally strict: chooser trigger,
family ladder quality, publication parity, CTA/apply, visual output, and
architecture compliance. This runner first proves whether each family has the
current structural hooks needed to run that audit honestly. If any requested
family is not structurally ready, it writes the per-family/global reports and
stops before fabricating live visual/apply results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.family_classification_runtime import (  # noqa: E402
    FAMILY_PREDICATES,
    classify_family_from_whole_beam_evidence,
)
from design_brain.families.registry import family_strategy_for  # noqa: E402
from optimisation_config import get_target_utilisation_band  # noqa: E402
from tools.verification.design_guide_family_browser_live_visual_consistency_snapshot import (  # noqa: E402
    _capture_visual_snapshot,
    _datetime_stamp,
    _wait_for_final_design_guide_card,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    TRACER_PATH,
    _load_browser_state,
    _query,
    _terminate_process_tree,
    _start_streamlit,
    _wait_for_http,
    _wait_for_run_end,
    _wait_for_solver_state,
)
from tools.verification.recipes.one_click_recipe_defs import find_named_case  # noqa: E402


FAMILIES: tuple[str, ...] = (
    "BENDING_FAIL_GOVERNS",
    "SHEAR_FAIL_GOVERNS",
    "BENDING_OVERDESIGN_GOVERNS",
    "SHEAR_OVERDESIGN_GOVERNS",
    "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
    "COMBINED_OVERDESIGN_GOVERNS",
    "SERVICEABILITY_GOVERNS",
)
NON_EXECUTABLE_CLASSIFICATION_STATES: tuple[str, ...] = (
    "MIN_BENDING_REO_GOVERNS",
    "MIN_SHEAR_REO_GOVERNS",
    "GEOMETRY_DETAILING_GOVERNS",
    "LOCKED_NO_REPAIR",
    "TARGET_BAND_REACHED",
    "EXACT_STOP_PROVEN",
)

FAMILY_CLASSIFICATION_ALIASES: dict[str, tuple[str, ...]] = {
    "SHEAR_FAIL_GOVERNS": (
        "SHEAR_FAIL_GOVERNS",
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
    ),
    "COMBINED_BENDING_SHEAR_FAIL_GOVERNS": (
        "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
        "COMBINED_BENDING_SHEAR_FAIL",
        "BENDING_AND_SHEAR_FAIL_GOVERN",
        "COMBINED_BENDING_SHEAR_FAIL_GOVERN",
    ),
    "COMBINED_BENDING_SHEAR_FAIL": (
        "COMBINED_BENDING_SHEAR_FAIL",
        "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
        "BENDING_AND_SHEAR_FAIL_GOVERN",
        "COMBINED_BENDING_SHEAR_FAIL_GOVERN",
    ),
    "COMBINED_OVERDESIGN_GOVERNS": (
        "COMBINED_OVERDESIGN_GOVERNS",
        "COMBINED_OVERDESIGN",
    ),
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS": (
        "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        "BENDING_FAIL_SHEAR_OPTIMISE_GOVERNS",
    ),
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS": (
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        "SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS",
        "SHEAR_FAIL_GOVERNS",
    ),
}

LIVE_AUDIT_PROBE_MAPPINGS: dict[str, dict[str, Any]] = {
    "BENDING_FAIL_GOVERNS": {
        "browser_recipe": "MATRIX_SHEAR_IN_TARGET_BENDING_FAIL",
        "visual_probe": "tools/verification/design_guide_browser_live_visual_consistency_snapshot.py",
        "apply_probe": "tools/verification/design_guide_bending_fail_no_button_root_audit.py",
        "expected_apply_surface": "executor-backed bending repair CTA",
    },
    "SHEAR_FAIL_GOVERNS": {
        "browser_recipe": "R2A_M0_V400",
        "visual_probe": "tools/verification/design_guide_browser_live_visual_consistency_snapshot.py",
        "apply_probe": "tools/verification/design_guide_unlocked_shear_apply_cta_publication_snapshot.py",
        "expected_apply_surface": "executor-backed shear repair CTA",
    },
    "COMBINED_BENDING_SHEAR_FAIL_GOVERNS": {
        "browser_recipe": "R3A_M300_V400",
        "visual_probe": "tools/verification/design_guide_browser_live_visual_consistency_snapshot.py",
        "apply_probe": "tools/verification/design_guide_partial_family_apply_effect_noop_proof.py",
        "expected_apply_surface": "combined fail repair CTA or explicit contract-defined engineering blocker",
    },
    "COMBINED_BENDING_SHEAR_FAIL": {
        "browser_recipe": "R3A_M300_V400",
        "visual_probe": "tools/verification/design_guide_browser_live_visual_consistency_snapshot.py",
        "apply_probe": "tools/verification/design_guide_partial_family_apply_effect_noop_proof.py",
        "expected_apply_surface": "combined fail repair CTA or explicit contract-defined engineering blocker",
    },
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS": {
        "browser_recipe": "R1A_M300_V0",
        "visual_probe": "tools/verification/design_guide_browser_live_visual_consistency_snapshot.py",
        "apply_probe": "tools/verification/families/bending_fail_shear_overdesign_governs_lock_verifier.py",
        "expected_apply_surface": "bending repair with shear-overdesign evidence CTA",
    },
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS": {
        "browser_recipe": "R2A_M0_V400",
        "visual_probe": "tools/verification/design_guide_browser_live_visual_consistency_snapshot.py",
        "apply_probe": "tools/verification/families/shear_fail_bending_overdesign_governs_lock_verifier.py",
        "expected_apply_surface": "shear repair with bending-overdesign evidence CTA",
    },
    "BENDING_OVERDESIGN_GOVERNS": {
        "browser_recipe": "OPT_EXPECT_BENDING_SAFE_OVERDESIGNED",
        "visual_probe": "tools/verification/design_guide_browser_live_visual_consistency_snapshot.py",
        "apply_probe": "tools/verification/design_guide_partial_family_apply_effect_noop_proof.py",
        "expected_apply_surface": "executor-backed bending cleanup CTA or explicit contract-defined engineering blocker",
    },
    "SHEAR_OVERDESIGN_GOVERNS": {
        "browser_recipe": "R5A_M0_V150",
        "visual_probe": "tools/verification/design_guide_browser_live_visual_consistency_snapshot.py",
        "apply_probe": "tools/verification/design_guide_partial_family_apply_effect_noop_proof.py",
        "expected_apply_surface": "executor-backed shear cleanup CTA or explicit contract-defined engineering blocker",
    },
    "COMBINED_OVERDESIGN": {
        "browser_recipe": "OPT_EXPECT_COMBINED_SAFE_OVERDESIGNED",
        "visual_probe": "tools/verification/design_guide_browser_live_visual_consistency_snapshot.py",
        "apply_probe": "tools/verification/families/combined_overdesign_governs_locked_regression.py",
        "expected_apply_surface": "combined cleanup CTA and stale-shell recovery regression",
    },
    "COMBINED_OVERDESIGN_GOVERNS": {
        "browser_recipe": "OPT_EXPECT_COMBINED_SAFE_OVERDESIGNED",
        "visual_probe": "tools/verification/design_guide_browser_live_visual_consistency_snapshot.py",
        "apply_probe": "tools/verification/families/combined_overdesign_governs_locked_regression.py",
        "expected_apply_surface": "combined cleanup CTA and stale-shell recovery regression",
    },
    "SERVICEABILITY_GOVERNS": {
        "browser_recipe": "MATRIX_CRACK_SERVICEABILITY_ONLY_FAIL",
        "visual_probe": "tools/verification/design_guide_browser_live_visual_consistency_snapshot.py",
        "apply_probe": "tools/verification/families/serviceability_governs_locked_regression.py",
        "expected_apply_surface": "serviceability blocked/exact-stop publication with no family-owned apply CTA",
    },
}

LIVE_AUDIT_RECIPE_MATRICES: dict[str, tuple[str, ...]] = {
    family: tuple(f"LIVE_FUZZ_{family}_{index:02d}" for index in range(1, 11))
    for family in (
        "BENDING_FAIL_GOVERNS",
        "SHEAR_FAIL_GOVERNS",
        "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
        "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        "BENDING_OVERDESIGN_GOVERNS",
        "SHEAR_OVERDESIGN_GOVERNS",
        "COMBINED_OVERDESIGN_GOVERNS",
        "SERVICEABILITY_GOVERNS",
    )
}
LIVE_AUDIT_RECIPE_MATRICES["COMBINED_BENDING_SHEAR_FAIL"] = LIVE_AUDIT_RECIPE_MATRICES[
    "COMBINED_BENDING_SHEAR_FAIL_GOVERNS"
]
LIVE_AUDIT_RECIPE_MATRICES["COMBINED_OVERDESIGN"] = LIVE_AUDIT_RECIPE_MATRICES[
    "COMBINED_OVERDESIGN_GOVERNS"
]

REPORT_DIR = ROOT / "artifacts" / "reports" / "family_fuzz"
VISUAL_DIR = ROOT / "artifacts" / "reports" / "family_fuzz_visuals"
VERIFY_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
FAMILIES_DIR = ROOT / "design_brain" / "families"
FAMILY_VERIFIER_DIR = ROOT / "tools" / "verification" / "families"
CONTRACT_ARTIFACT_DIR = ROOT / "artifacts" / "contracts" / "families"
LIVE_EXECUTABLE_FAMILIES = {
    "BENDING_FAIL_GOVERNS",
    "SHEAR_FAIL_GOVERNS",
    "BENDING_OVERDESIGN_GOVERNS",
    "SHEAR_OVERDESIGN_GOVERNS",
    "COMBINED_BENDING_SHEAR_FAIL",
    "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
    "COMBINED_OVERDESIGN",
    "COMBINED_OVERDESIGN_GOVERNS",
    "SERVICEABILITY_GOVERNS",
}
LIVE_ACTION_REQUIRED_FAMILIES = {
    "BENDING_FAIL_GOVERNS",
    "SHEAR_FAIL_GOVERNS",
    "BENDING_OVERDESIGN_GOVERNS",
    "SHEAR_OVERDESIGN_GOVERNS",
    "COMBINED_BENDING_SHEAR_FAIL",
    "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
    "COMBINED_OVERDESIGN",
    "COMBINED_OVERDESIGN_GOVERNS",
}
LIVE_ACTION_BUTTON_TEXTS = (
    "Run one-click auto design",
    "Apply:",
    "Apply recommendation",
    "Apply proposed change",
    "Improve design",
    "Repair preview",
)

TARGET_BAND_EPS = 0.005


def _target_domains_for_family(family: str) -> tuple[str, ...]:
    family_u = str(family or "").upper()
    if "COMBINED" in family_u:
        return ("bending", "shear")
    domains: list[str] = []
    if "BENDING" in family_u:
        domains.append("bending")
    if "SHEAR" in family_u:
        domains.append("shear")
    return tuple(domains)


def _stable_seed(seed: int, family: str, index: int) -> random.Random:
    value = f"{seed}:{family}:{index}"
    acc = 0
    for char in value:
        acc = (acc * 131 + ord(char)) % (2**32)
    return random.Random(acc)


def _state_for_family(family: str, index: int, seed: int) -> dict[str, Any]:
    rng = _stable_seed(seed, family, index)
    jitter = rng.uniform(-0.02, 0.02)
    base = {
        "bending_utilisation": 0.92 + jitter,
        "shear_utilisation": 0.92 - jitter,
        "bending_state": "TARGET",
        "shear_state": "TARGET",
        "serviceability_state": "PASS",
        "geometry_detailing_state": "PASS",
        "minimum_bending_reo_state": "PASS",
        "minimum_shear_reo_state": "PASS",
        "geometry_locked": False,
        "reo_locked": False,
        "can_strengthen_bending": False,
        "can_strengthen_shear": False,
        "can_optimise_bending_without_hurting_shear": False,
        "can_optimise_shear_without_hurting_bending": False,
        "exact_stop_available": False,
        "no_valid_repair_available": False,
        "zero_shear_with_ligatures": False,
        "unnecessary_shear_reinforcement_exists": False,
        "shear_cleanup_possible": False,
        "scenario_index": index,
        "scenario_seed": seed,
    }
    if family == "BENDING_FAIL_GOVERNS":
        base.update(
            bending_utilisation=1.12 + index * 0.015,
            shear_utilisation=0.91,
            bending_state="FAIL",
            can_strengthen_bending=True,
        )
    elif family == "SHEAR_FAIL_GOVERNS":
        base.update(
            bending_utilisation=0.91,
            shear_utilisation=1.12 + index * 0.015,
            shear_state="FAIL",
            can_strengthen_shear=True,
        )
    elif family in {"COMBINED_BENDING_SHEAR_FAIL", "COMBINED_BENDING_SHEAR_FAIL_GOVERNS"}:
        base.update(
            bending_utilisation=1.10 + index * 0.012,
            shear_utilisation=1.13 + index * 0.01,
            bending_state="FAIL",
            shear_state="FAIL",
            can_strengthen_bending=True,
            can_strengthen_shear=True,
        )
    elif family == "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS":
        base.update(
            bending_utilisation=1.12 + index * 0.012,
            shear_utilisation=0.63 + index * 0.004,
            bending_state="FAIL",
            shear_state="OVERDESIGNED",
            can_strengthen_bending=True,
            can_optimise_shear_without_hurting_bending=True,
        )
    elif family == "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS":
        base.update(
            bending_utilisation=0.63 + index * 0.004,
            shear_utilisation=1.12 + index * 0.012,
            bending_state="OVERDESIGNED",
            shear_state="FAIL",
            can_strengthen_shear=True,
            can_optimise_bending_without_hurting_shear=True,
        )
    elif family == "BENDING_OVERDESIGN_GOVERNS":
        base.update(
            bending_utilisation=0.62 + index * 0.01,
            shear_utilisation=0.91,
            bending_state="OVERDESIGNED",
            can_optimise_bending_without_hurting_shear=True,
        )
    elif family == "SHEAR_OVERDESIGN_GOVERNS":
        base.update(
            bending_utilisation=0.91,
            shear_utilisation=0.62 + index * 0.01,
            shear_state="OVERDESIGNED",
            can_optimise_shear_without_hurting_bending=True,
        )
    elif family in {"COMBINED_OVERDESIGN", "COMBINED_OVERDESIGN_GOVERNS"}:
        base.update(
            bending_utilisation=0.62 + index * 0.008,
            shear_utilisation=0.63 + index * 0.008,
            bending_state="OVERDESIGNED",
            shear_state="OVERDESIGNED",
            can_optimise_bending_without_hurting_shear=True,
            can_optimise_shear_without_hurting_bending=True,
        )
    elif family == "MIN_BENDING_REO_GOVERNS":
        base.update(
            bending_utilisation=0.90,
            shear_utilisation=0.91,
            minimum_bending_reo_state="GOVERNS",
        )
    elif family == "MIN_SHEAR_REO_GOVERNS":
        base.update(
            bending_utilisation=0.91,
            shear_utilisation=0.90,
            minimum_shear_reo_state="GOVERNS",
        )
    elif family == "GEOMETRY_DETAILING_GOVERNS":
        base.update(
            geometry_detailing_state="BLOCKED",
            geometry_locked=True,
        )
    elif family == "SERVICEABILITY_GOVERNS":
        base.update(
            serviceability_state="FAIL",
        )
    elif family == "LOCKED_NO_REPAIR":
        base.update(
            bending_utilisation=0.94,
            shear_utilisation=1.12 + index * 0.01,
            shear_state="FAIL",
            geometry_locked=True,
            reo_locked=True,
            no_valid_repair_available=True,
        )
    elif family == "TARGET_BAND_REACHED":
        base.update(
            bending_utilisation=0.90 + index * 0.003,
            shear_utilisation=0.91 - index * 0.002,
        )
    elif family == "EXACT_STOP_PROVEN":
        base.update(
            bending_utilisation=0.93,
            shear_utilisation=0.94,
            exact_stop_available=True,
        )
    return base


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")


def _contract_paths_for_family(family: str) -> list[Path]:
    matches: list[Path] = []
    for path in FAMILIES_DIR.glob("*/contract.json"):
        data = _read_json(path)
        identity = data.get("family_identity", {})
        ids = {
            str(identity.get("family_id") or "").upper(),
            str(identity.get("runtime_family_id") or "").upper(),
            str(data.get("family_id") or "").upper(),
            str(data.get("runtime_family_id") or "").upper(),
        }
        if family in ids:
            matches.append(path)
    artifact_guess = CONTRACT_ARTIFACT_DIR / f"{family.lower()}.json"
    if artifact_guess.exists():
        matches.append(artifact_guess)
    return sorted(set(matches))


def _matching_family_verifiers(family: str, term: str | None = None) -> list[Path]:
    token = _normalise(family)
    loose = token.replace("_governs", "").replace("_govern", "")
    matches: list[Path] = []
    for path in FAMILY_VERIFIER_DIR.glob("*.py"):
        stem = _normalise(path.stem)
        if term and term not in stem:
            continue
        if token in stem or loose in stem:
            matches.append(path)
    return sorted(matches)


def _strategy_ladder_methods(strategy: Any) -> list[str]:
    if strategy is None:
        return []
    names = (
        "contracted_repair_ladder_specs",
        "contracted_optimisation_ladder_specs",
        "contracted_serviceability_ladder_specs",
        "contracted_serviceability_ladder_result",
        "contracted_stop_ladder_specs",
        "contracted_mixed_ladder_result",
    )
    return [name for name in names if callable(getattr(strategy, name, None))]


def _scenario_trigger_rows(family: str, seed: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    accepted_family_ids = set(FAMILY_CLASSIFICATION_ALIASES.get(family, (family,)))
    for index in range(10):
        evidence = _state_for_family(family, index, seed)
        result = classify_family_from_whole_beam_evidence(evidence)
        selected = str(result.get("selected_family_id") or "")
        trigger_passed = selected in accepted_family_ids
        rows.append(
            {
                "scenario_id": f"{family}_FUZZ_{index + 1:02d}",
                "input_evidence": evidence,
                "expected_family": family,
                "actual_selected_family": selected,
                "accepted_family_ids": sorted(accepted_family_ids),
                "classification_alias_used": selected != family and trigger_passed,
                "matched_family_ids": list(result.get("matched_family_ids") or []),
                "selection_reason": result.get("classification_reason"),
                "classification_hash": result.get("classification_hash"),
                "trigger_passed": trigger_passed,
            }
        )
    return rows


def _live_recipe_matrix_status(family: str, scenario_count: int) -> dict[str, Any]:
    recipes = list(LIVE_AUDIT_RECIPE_MATRICES.get(family) or ())
    resolved = [(recipe, find_named_case(recipe)) for recipe in recipes]
    known = [recipe for recipe, case in resolved if case]
    unknown = [recipe for recipe, case in resolved if not case]
    unique_name_count = len(set(recipes))
    payload_fingerprints = [
        hashlib.sha256(
            json.dumps(
                dict(case.get("changes") or {}),
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        for _recipe, case in resolved
        if case
    ]
    unique_payload_count = len(set(payload_fingerprints))
    all_names_distinct = unique_name_count == len(recipes)
    all_payloads_distinct = unique_payload_count == len(recipes)
    return {
        "family": family,
        "scenario_count": scenario_count,
        "recipes": recipes,
        "recipe_count": len(recipes),
        "unique_recipe_count": unique_name_count,
        "unique_recipe_payload_count": unique_payload_count,
        "known_recipe_count": len(known),
        "unknown_recipes": unknown,
        "has_one_recipe_per_scenario": len(recipes) == scenario_count,
        "all_recipe_names_distinct": all_names_distinct,
        "all_recipe_payloads_distinct": all_payloads_distinct,
        "all_recipes_distinct": all_names_distinct and all_payloads_distinct,
        "all_recipes_known": len(known) == len(recipes),
        "ready": bool(
            scenario_count > 0
            and len(recipes) == scenario_count
            and all_names_distinct
            and all_payloads_distinct
            and len(known) == len(recipes)
        ),
    }


def _attach_live_recipe_matrix(family: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recipes = list(LIVE_AUDIT_RECIPE_MATRICES.get(family) or ())
    if len(recipes) != len(rows):
        return rows
    enriched: list[dict[str, Any]] = []
    for row, recipe in zip(rows, recipes, strict=True):
        next_row = dict(row)
        next_row["browser_recipe"] = recipe
        enriched.append(next_row)
    return enriched


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _typed_apply_commit_proven(run_end_event: dict[str, Any] | None) -> bool:
    run_end = _safe_dict(run_end_event)
    run_data = _safe_dict(run_end.get("data"))
    route = _safe_dict(run_data.get("last_apply_route"))
    compare = _safe_dict(run_data.get("compare"))
    final_updates = _safe_dict(
        run_data.get("final_updates") or compare.get("final_updates")
    )
    applied_updates = _safe_dict(route.get("applied_updates"))
    applied_updates_cover_trace = bool(final_updates) and all(
        key in applied_updates and applied_updates[key] == value
        for key, value in final_updates.items()
    )
    return bool(
        str(run_data.get("status") or "").lower() == "pass"
        and str(run_data.get("stop_reason") or "") == "typed_apply_committed"
        and route.get("typed_apply_canonical_candidate_preverified") is True
        and route.get("post_apply_all_key_pass") is True
        and route.get("post_apply_any_fail") is False
        and route.get("payload_binding_match") is True
        and route.get("payload_update_match") is True
        and applied_updates
        and applied_updates_cover_trace
    )


def _apply_update_value_matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, bool) or isinstance(actual, bool):
        return actual is expected
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(actual) - float(expected)) <= 1e-6
    return actual == expected


_LONGITUDINAL_ALIAS_TO_CANONICAL: tuple[tuple[str, str], ...] = (
    ("bot1_count", "bot_row_1_bars"),
    ("db_bot_1", "bot_row_1_dia"),
    ("bot1_layout_mode", "bot_row_1_mode"),
    ("bot1_spacing", "bot_row_1_spacing"),
    ("bot2_count", "bot_row_2_bars"),
    ("db_bot_2", "bot_row_2_dia"),
    ("bot2_layout_mode", "bot_row_2_mode"),
    ("bot2_spacing", "bot_row_2_spacing"),
    ("top1_count", "top_row_1_bars"),
    ("db_top_1", "top_row_1_dia"),
    ("top1_layout_mode", "top_row_1_mode"),
    ("top1_spacing", "top_row_1_spacing"),
    ("top2_count", "top_row_2_bars"),
    ("db_top_2", "top_row_2_dia"),
    ("top2_layout_mode", "top_row_2_mode"),
    ("top2_spacing", "top_row_2_spacing"),
)


def _canonical_post_apply_update_expectations(
    applied_updates: dict[str, Any],
) -> dict[str, Any]:
    """Return material canonical fields for post-Apply browser proof.

    Typed Apply still commits legacy aliases atomically so older widget/session
    consumers remain synchronized. Those aliases are projections, not
    independent engineering authorities: count-mode spacing may be normalized
    for display, and diameter/spacing/mode are immaterial for an inactive row.
    Browser proof must therefore require the canonical row model while still
    failing every material canonical mismatch.
    """

    canonical = dict(applied_updates)
    for alias_key, canonical_key in _LONGITUDINAL_ALIAS_TO_CANONICAL:
        if canonical_key in canonical:
            canonical.pop(alias_key, None)
        elif alias_key in canonical:
            canonical[canonical_key] = canonical.pop(alias_key)

    for section in ("bot", "top"):
        for row_number in (1, 2):
            bars_key = f"{section}_row_{row_number}_bars"
            if bars_key not in canonical:
                continue
            try:
                inactive = int(float(canonical.get(bars_key) or 0)) <= 0
            except (TypeError, ValueError):
                inactive = False
            if not inactive:
                continue
            for suffix in ("dia", "mode", "spacing"):
                canonical.pop(
                    f"{section}_row_{row_number}_{suffix}",
                    None,
                )
    try:
        links_inactive = (
            "lig_d" in canonical
            and "lig_legs" in canonical
            and (
                int(float(canonical.get("lig_d") or 0)) <= 0
                or int(float(canonical.get("lig_legs") or 0)) <= 0
            )
        )
    except (TypeError, ValueError):
        links_inactive = False
    if links_inactive:
        # Link spacing has no engineering meaning when the canonical link
        # diameter/leg count disables shear reinforcement. The session keeps
        # a valid display spacing for a future re-enable.
        canonical.pop("s_lig", None)
    return canonical


def _post_apply_update_match_probe(
    browser_state: dict[str, Any],
    applied_updates: dict[str, Any],
) -> dict[str, Any]:
    shared = _safe_dict(browser_state.get("browser_shared_probe"))
    summary = _safe_dict(browser_state.get("summary_state_probe"))
    rows: dict[str, dict[str, Any]] = {}
    for key, expected in applied_updates.items():
        shared_publishes = key in shared
        summary_publishes = key in summary
        shared_match = bool(
            shared_publishes
            and _apply_update_value_matches(shared.get(key), expected)
        )
        summary_match = bool(
            summary_publishes
            and _apply_update_value_matches(summary.get(key), expected)
        )
        rows[str(key)] = {
            "expected": expected,
            "shared_publishes": shared_publishes,
            "shared_actual": shared.get(key),
            "shared_match": shared_match,
            "summary_publishes": summary_publishes,
            "summary_actual": summary.get(key),
            "summary_match": summary_match,
            "published_source_present": bool(shared_publishes or summary_publishes),
            "all_published_sources_match": bool(
                (not shared_publishes or shared_match)
                and (not summary_publishes or summary_match)
            ),
        }
    return {
        "updates": rows,
        "all_updates_published": bool(
            rows
            and all(row["published_source_present"] for row in rows.values())
        ),
        "all_published_sources_match": bool(
            rows
            and all(row["all_published_sources_match"] for row in rows.values())
        ),
    }


def _render_rerun_seq(browser_state: dict[str, Any]) -> Any:
    return _safe_dict(browser_state.get("render_timing_probe")).get("rerun_seq")


def _state_engineering_hash(browser_state: dict[str, Any]) -> Any:
    return (
        browser_state.get("engineering_hash")
        or _safe_dict(browser_state.get("workspace_result_probe")).get(
            "engineering_hash"
        )
        or _safe_dict(browser_state.get("authoritative_result_probe")).get(
            "engineering_hash"
        )
        or _safe_dict(
            browser_state.get("_authoritative_design_result_runtime_probe")
        ).get("engineering_hash")
    )


def _wait_for_authoritative_post_apply_state(
    page,
    *,
    before_state: dict[str, Any],
    applied_updates: dict[str, Any],
    timeout_s: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Wait for committed Apply values to reach authoritative browser output.

    A passing executor trace proves that the write was accepted; it does not
    prove that Streamlit has completed the following application transaction.
    The browser result is safe to judge only after the committed values are
    projected, the calculation overview is terminal, and the final
    publication has advanced to the post-Apply PASS result.
    """

    deadline = time.monotonic() + max(1.0, float(timeout_s))
    started = time.monotonic()
    before_publication = _extract_publication_probe(before_state)
    before_publication_identity = (
        before_publication.get("authority_hash")
        or before_publication.get("publication_hash")
    )
    before_rerun_seq = _render_rerun_seq(before_state)
    before_engineering_hash = _state_engineering_hash(before_state)
    authoritative_updates = _canonical_post_apply_update_expectations(
        applied_updates
    )
    samples: list[dict[str, Any]] = []
    last_state: dict[str, Any] = dict(before_state)
    final_conditions: dict[str, Any] = {}

    while time.monotonic() < deadline:
        try:
            candidate = _load_browser_state(
                page,
                fallback_timeout_ms=1_000,
                preferred_updates=authoritative_updates,
            )
        except Exception as exc:
            samples.append(
                {
                    "elapsed_ms": int((time.monotonic() - started) * 1000),
                    "load_error": f"{type(exc).__name__}:{exc}",
                }
            )
            page.wait_for_timeout(300)
            continue
        if not isinstance(candidate, dict):
            page.wait_for_timeout(300)
            continue

        last_state = dict(candidate)
        update_probe = _post_apply_update_match_probe(
            last_state,
            authoritative_updates,
        )
        overview = _safe_dict(last_state.get("summary_overview_probe"))
        overview_terminal_pass = bool(
            overview.get("all_key_pass") is True
            and overview.get("any_fail") is False
        )
        publication = _extract_publication_probe(last_state)
        publication_identity = (
            publication.get("authority_hash")
            or publication.get("publication_hash")
        )
        publication_terminal_pass = bool(
            str(publication.get("outcome_state") or "").upper() == "PASS"
            and not bool(
                _safe_dict(publication.get("cta")).get("enabled")
                or _safe_dict(publication.get("cta")).get("actionable")
            )
        )
        rerun_seq = _render_rerun_seq(last_state)
        engineering_hash = _state_engineering_hash(last_state)
        authoritative_state_advanced = bool(
            (
                rerun_seq is not None
                and before_rerun_seq is not None
                and rerun_seq != before_rerun_seq
            )
            or (
                engineering_hash
                and before_engineering_hash
                and engineering_hash != before_engineering_hash
            )
            or (
                publication_identity
                and before_publication_identity
                and publication_identity != before_publication_identity
            )
        )
        final_conditions = {
            "applied_updates_published": update_probe.get(
                "all_updates_published"
            ),
            "applied_updates_match": update_probe.get(
                "all_published_sources_match"
            ),
            "overview_terminal_pass": overview_terminal_pass,
            "publication_terminal_pass": publication_terminal_pass,
            "authoritative_state_advanced": authoritative_state_advanced,
        }
        samples.append(
            {
                "elapsed_ms": int((time.monotonic() - started) * 1000),
                "rerun_seq": rerun_seq,
                "engineering_hash": engineering_hash,
                "publication_identity": publication_identity,
                "publication_family": publication.get("selected_family_id"),
                "publication_outcome": publication.get("outcome_state"),
                "overview_all_key_pass": overview.get("all_key_pass"),
                "overview_any_fail": overview.get("any_fail"),
                "update_match_probe": update_probe,
                "conditions": dict(final_conditions),
            }
        )
        if all(final_conditions.values()):
            return last_state, {
                "settled": True,
                "reason": "authoritative_post_apply_transaction_published",
                "elapsed_ms": int((time.monotonic() - started) * 1000),
                "applied_updates": dict(applied_updates),
                "authoritative_updates_checked": dict(authoritative_updates),
                "before": {
                    "rerun_seq": before_rerun_seq,
                    "engineering_hash": before_engineering_hash,
                    "publication_identity": before_publication_identity,
                },
                "final_conditions": dict(final_conditions),
                "samples": samples,
            }
        page.wait_for_timeout(350)

    return last_state, {
        "settled": False,
        "reason": "authoritative_post_apply_transaction_not_published_before_timeout",
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "applied_updates": dict(applied_updates),
        "authoritative_updates_checked": dict(authoritative_updates),
        "before": {
            "rerun_seq": before_rerun_seq,
            "engineering_hash": before_engineering_hash,
            "publication_identity": before_publication_identity,
        },
        "final_conditions": dict(final_conditions),
        "samples": samples,
    }


def _extract_publication_probe(browser_state: dict[str, Any]) -> dict[str, Any]:
    final_payload = _safe_dict(browser_state.get("final_publication_verifier_payload"))
    final_publication = _safe_dict(browser_state.get("final_design_guide_publication"))
    display_payload = _safe_dict(final_payload.get("display"))
    cta_payload = _safe_dict(final_payload.get("cta"))
    evidence_payload = _safe_dict(final_payload.get("evidence"))
    button_contract = _safe_dict(browser_state.get("primary_button_contract"))
    card_attrs = _safe_dict(browser_state.get("card_data_attributes"))
    debug_sources = _safe_dict(browser_state.get("browser_debug_sources"))
    debug_source_values = [
        _safe_dict(value)
        for value in debug_sources.values()
        if isinstance(value, dict)
    ]
    nested_debug_values: list[dict[str, Any]] = []
    for value in debug_source_values:
        for key in (
            "button_contract",
            "primary_button_contract",
            "displayed_primary_button_contract",
            "candidate_search_evidence",
            "selection_evidence",
            "display_truth",
            "final_publication_verifier_payload",
        ):
            nested = value.get(key)
            if isinstance(nested, dict):
                nested_debug_values.append(dict(nested))

    def _truthy(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "true", "yes", "y", "enabled", "action", "actionable"}

    def _first_from_sources(keys: tuple[str, ...], sources: list[dict[str, Any]]) -> Any:
        for source in sources:
            for key in keys:
                value = source.get(key)
                if value not in (None, "", [], {}):
                    return value
        return None

    source_values = [
        final_payload,
        evidence_payload,
        display_payload,
        _safe_dict(display_payload.get("details")),
        button_contract,
        card_attrs,
        *debug_source_values,
        *nested_debug_values,
        final_publication,
    ]
    selected_family_id = (
        _first_from_sources(
            (
                "selected_family_id",
                "selected_family",
                "published_family_id",
                "family",
                "cta_family_id",
                "apply_payload_family_id",
            ),
            source_values,
        )
    )
    cta_family_id = (
        cta_payload.get("family_id")
        or cta_payload.get("family")
        or cta_payload.get("cta_family_id")
        or _first_from_sources(
            (
                "family_id",
                "family",
                "cta_family_id",
                "selected_family_id",
                "published_family_id",
                "apply_payload_family_id",
            ),
            [button_contract, card_attrs, *debug_source_values, *nested_debug_values],
        )
    )
    selected_family_id = selected_family_id or cta_family_id
    cta_sources = [cta_payload, button_contract, card_attrs, *nested_debug_values, *debug_source_values]
    enabled_cta_source = next(
        (
            source
            for source in cta_sources
            if isinstance(source, dict)
            and (_truthy(source.get("enabled")) or _truthy(source.get("actionable")) or _truthy(source.get("render_cta_enabled")))
        ),
        {},
    )
    final_outcome_hint = str(
        final_payload.get("outcome_state")
        or display_payload.get("outcome_state")
        or display_payload.get("status")
        or display_payload.get("display_state")
        or ""
    ).strip().upper()
    final_cta_is_terminal_no_action = bool(
        final_outcome_hint in {"PASS", "BLOCKED", "ERROR", "PROOF_PENDING"}
        and cta_payload
        and not (_truthy(cta_payload.get("enabled")) or _truthy(cta_payload.get("actionable")))
    )
    if (
        enabled_cta_source
        and not final_cta_is_terminal_no_action
        and not (_truthy(cta_payload.get("enabled")) or _truthy(cta_payload.get("actionable")))
    ):
        cta_payload = dict(enabled_cta_source)
        cta_family_id = (
            cta_payload.get("family_id")
            or cta_payload.get("family")
            or cta_payload.get("cta_family_id")
            or selected_family_id
            or cta_family_id
        )
        selected_family_id = selected_family_id or cta_family_id
    if not cta_payload and cta_family_id:
        cta_payload = {
            "family_id": cta_family_id,
            "enabled": bool(button_contract.get("enabled") or button_contract.get("actionable")),
            "actionable": bool(button_contract.get("actionable") or button_contract.get("enabled")),
            "intent": button_contract.get("intent") or button_contract.get("action_type"),
        }
    elif cta_payload and cta_family_id:
        cta_payload.setdefault("family_id", cta_family_id)
        cta_payload.setdefault("cta_family_id", cta_family_id)
    outcome_state = (
        final_payload.get("outcome_state")
        or display_payload.get("outcome_state")
        or _first_from_sources(("outcome_state", "display_state", "status"), source_values)
    )
    outcome_text = str(outcome_state or "").strip().upper()
    if outcome_text not in {"ACTION", "PASS", "BLOCKED", "ERROR", "PROOF_PENDING"}:
        outcome_text = ""
    if not outcome_text and (_truthy(cta_payload.get("enabled")) or _truthy(cta_payload.get("actionable"))):
        outcome_text = "ACTION"
    if not outcome_text:
        status_text = str(
            display_payload.get("status")
            or display_payload.get("display_state")
            or display_payload.get("badge")
            or card_attrs.get("status")
            or ""
        ).strip().upper()
        if status_text in {"PASS", "GOOD", "OK"}:
            outcome_text = "PASS"
        elif status_text in {"BLOCKED", "ERROR"}:
            outcome_text = status_text
    publication_title = (
        display_payload.get("title")
        or button_contract.get("title")
        or _first_from_sources(("title", "title_main", "selected_title"), source_values)
    )
    blocker_reason = (
        final_payload.get("blocker_reason")
        or evidence_payload.get("blocker_reason")
        or display_payload.get("blocker_reason")
        or _first_from_sources(("blocker_reason", "blocking_reason", "disabled_reason"), source_values)
    )
    if (
        not outcome_text
        and str(blocker_reason or "").strip().lower()
        in {"terminal_pass_no_action", "terminal_overdesign_cleanup_no_second_cta"}
        and not (_truthy(cta_payload.get("enabled")) or _truthy(cta_payload.get("actionable")))
    ):
        outcome_text = "PASS"
    if (
        not outcome_text
        and "blocked" in str(publication_title or "").strip().lower()
        and not (_truthy(cta_payload.get("enabled")) or _truthy(cta_payload.get("actionable")))
    ):
        outcome_text = "BLOCKED"
    cta_summary = _safe_dict(cta_payload.get("apply_payload_summary"))
    cta_handoff = _safe_dict(cta_payload.get("one_click_action_handoff"))
    terminal_cta_has_executable_handoff = bool(
        _safe_dict(cta_summary.get("updates"))
        or _truthy(cta_handoff.get("has_updates"))
        or _safe_dict(cta_handoff.get("updates"))
    )
    if (
        outcome_text in {"PASS", "BLOCKED", "ERROR", "PROOF_PENDING"}
        and (final_cta_is_terminal_no_action or not terminal_cta_has_executable_handoff)
    ):
        cta_payload = {
            **dict(cta_payload),
            "enabled": False,
            "actionable": False,
            "action_type": None,
            "updates": {},
        }
        summary = _safe_dict(cta_payload.get("apply_payload_summary"))
        if summary:
            summary["action_type"] = None
            summary["updates"] = {}
            cta_payload["apply_payload_summary"] = summary
        handoff = _safe_dict(cta_payload.get("one_click_action_handoff"))
        if handoff:
            handoff["action_type"] = None
            handoff["has_updates"] = False
            cta_payload["one_click_action_handoff"] = handoff
    return {
        "publication_hash": (
            final_payload.get("publication_hash")
            or final_publication.get("publication_hash")
            or _safe_dict(browser_state.get("final_publication_hashes")).get("publication_hash")
            or card_attrs.get("publication_hash")
        ),
        "authority_hash": (
            final_payload.get("final_publication_authority_hash")
            or _safe_dict(browser_state.get("final_publication_hashes")).get("final_publication_authority_hash")
            or _safe_dict(browser_state.get("final_publication_hashes")).get("authority_hash")
            or card_attrs.get("authority_hash")
        ),
        "selected_family_id": selected_family_id,
        "outcome_state": outcome_text or None,
        "title": publication_title,
        "status": display_payload.get("status") or final_payload.get("status") or _first_from_sources(("status", "display_state"), source_values),
        "blocker_reason": blocker_reason,
        "exact_stop_proof": _safe_dict(
            final_payload.get("exact_stop_proof")
            or evidence_payload.get("exact_stop_proof")
            or _first_from_sources(("exact_stop_proof", "exact_blockers_by_family"), source_values)
        ),
        "target_band_proof": _safe_dict(
            final_payload.get("target_band_proof")
            or evidence_payload.get("target_band_proof")
            or _first_from_sources(("target_band_proof", "target_band_evidence"), source_values)
        ),
        "cta": cta_payload,
        "primary_button_contract": button_contract,
        "debug_source_keys": sorted(debug_sources.keys())[:40],
    }


def _parse_util_float(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or text in {"-", "\u2014"}:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except Exception:
        return None


def _summary_domain_utils(snapshot: dict[str, Any]) -> dict[str, float | None]:
    browser_state = _safe_dict(snapshot.get("browser_state"))
    summary_overview = _safe_dict(browser_state.get("summary_overview_probe"))
    authoritative_utils = _safe_dict(summary_overview.get("utils"))
    authoritative = {
        "bending": _parse_util_float(authoritative_utils.get("bending")),
        "shear": _parse_util_float(authoritative_utils.get("shear")),
    }
    if any(value is not None for value in authoritative.values()):
        return authoritative
    cards = _safe_dict(snapshot.get("summary_cards"))
    return {
        "bending": _parse_util_float(_safe_dict(cards.get("bending_uls")).get("utilisation")),
        "shear": _parse_util_float(_safe_dict(cards.get("shear_uls")).get("utilisation")),
    }


def _visible_design_guide_utilisation(snapshot: dict[str, Any]) -> float | None:
    text = str(_safe_dict(snapshot.get("design_guide")).get("text_sample") or "")
    for pattern in (
        r"utilisation\s*=\s*(-?\d+(?:\.\d+)?)",
        r"utilization\s*=\s*(-?\d+(?:\.\d+)?)",
        r"utilisation\s+(-?\d+(?:\.\d+)?)",
        r"utilization\s+(-?\d+(?:\.\d+)?)",
    ):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except Exception:
                return None
    return None


def _publication_has_target_band_blocker(
    *,
    publication_probe: dict[str, Any],
    visual_snapshot: dict[str, Any],
) -> bool:
    text_parts = [
        publication_probe.get("title"),
        publication_probe.get("status"),
        publication_probe.get("blocker_reason"),
        json.dumps(publication_probe.get("exact_stop_proof") or {}, sort_keys=True),
        json.dumps(publication_probe.get("target_band_proof") or {}, sort_keys=True),
        _safe_dict(visual_snapshot.get("design_guide")).get("text_sample"),
    ]
    haystack = " ".join(str(part or "") for part in text_parts).lower()
    return bool(
        re.search(
            r"block|blocked|blocker|exhaust|exhausted|no valid|no safe|exact stop|exact-stop|"
            r"geometry locked|reinforcement locked|detailing|spacing|ductility|as_min|minimum reinforcement",
            haystack,
        )
    )


def _publication_has_explicit_engineering_blocker(publication_probe: dict[str, Any]) -> bool:
    probe = _safe_dict(publication_probe)
    cta = _safe_dict(probe.get("cta"))
    if (
        str(probe.get("outcome_state") or "").strip().upper() in {"BLOCKED", "PASS"}
        and not (cta.get("enabled") or cta.get("actionable"))
    ):
        return True
    stack: list[Any] = [_safe_dict(probe.get("exact_stop_proof"))]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            ident = id(current)
            if ident in seen:
                continue
            seen.add(ident)
            if current.get("no_second_cta_required") or current.get("best_safe_candidate_applied"):
                try:
                    executable_targets = int(
                        current.get("executable_target_band_candidate_count") or 0
                    )
                except Exception:
                    executable_targets = 0
                if executable_targets <= 0:
                    return True
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return False


def _accepted_browser_family_ids(family: str) -> set[str]:
    accepted = set(FAMILY_CLASSIFICATION_ALIASES.get(family, (family,)))
    if family == "SERVICEABILITY_GOVERNS":
        accepted.update({"SERVICEABILITY_GOVERNS", "SERVICEABILITY_GOVERNS_OPTIMISATION_STOP"})
    return {str(value or "").strip().upper() for value in accepted if str(value or "").strip()}


def _infer_visible_family_from_design_guide_text(text: str) -> str | None:
    haystack = str(text or "").strip().lower()
    if not haystack:
        return None
    if "crack" in haystack or "deflection" in haystack or "serviceability" in haystack:
        return "SERVICEABILITY_GOVERNS"
    cleanup_card = bool(
        "cleanup" in haystack
        or "one-click reduction" in haystack
        or "reduce section size" in haystack
        or "trim bottom reinforcement" in haystack
        or "overdesign" in haystack
        or "reserve" in haystack
    )
    if cleanup_card and "capacity is low" not in haystack:
        explicit_shear_cleanup = "shear links" in haystack
        shear_cleanup = bool(
            explicit_shear_cleanup
            or "stirrup" in haystack
            or "number of legs" in haystack
            or "link spacing" in haystack
            or "links:" in haystack
        )
        bending_cleanup = bool(
            "bottom reinforcement" in haystack
            or "bottom reo" in haystack
            or "section size" in haystack
            or "depth:" in haystack
            or "width:" in haystack
            or "geometry" in haystack
        )
        if explicit_shear_cleanup and bending_cleanup:
            return "COMBINED_OVERDESIGN_GOVERNS"
        if shear_cleanup:
            return "SHEAR_OVERDESIGN_GOVERNS"
        if bending_cleanup:
            return "BENDING_OVERDESIGN_GOVERNS"
        return None
    if "bending and shear" in haystack or "combined" in haystack:
        return "COMBINED_BENDING_SHEAR_FAIL_GOVERNS"
    if "shear capacity" in haystack or "link spacing" in haystack:
        return "SHEAR_FAIL_GOVERNS"
    if "bending capacity" in haystack or "bottom reinforcement" in haystack:
        return "BENDING_FAIL_GOVERNS"
    return None


def _browser_family_identity_contract(
    *,
    family: str,
    publication_probe: dict[str, Any],
    final_card_probe: dict[str, Any],
    visual_snapshot: dict[str, Any],
) -> dict[str, Any]:
    accepted = _accepted_browser_family_ids(family)
    probe_family = str(publication_probe.get("selected_family_id") or "").strip().upper()
    cta_family = str(_safe_dict(publication_probe.get("cta")).get("family_id") or "").strip().upper()
    card_titles = [
        str(title or "")
        for title in list(_safe_dict(_safe_dict(visual_snapshot.get("checks")).get("visible_design_guide_cards")).get("titles") or [])
    ]
    text_sample = str(final_card_probe.get("text_sample") or "")
    inferred_family = _infer_visible_family_from_design_guide_text(" ".join([text_sample, *card_titles]))
    visible_text_family = str(inferred_family or "").strip().upper()
    visible_contract_family = ""
    if probe_family and cta_family and probe_family == cta_family:
        visible_contract_family = probe_family
    visible_family = str(visible_contract_family or visible_text_family or "").strip().upper()
    observed_by_role = {
        "publication_selected_family_id": probe_family or None,
        "publication_cta_family_id": cta_family or None,
        "visible_inferred_family_id": visible_family or None,
    }
    missing_roles = [role for role, value in observed_by_role.items() if not value]
    mismatched_roles = [
        {"role": role, "actual": value}
        for role, value in observed_by_role.items()
        if value and value not in accepted
    ]
    observed = [value for value in observed_by_role.values() if value]
    return {
        "expected_family": family,
        "accepted_family_ids": sorted(accepted),
        "publication_selected_family_id": probe_family or None,
        "publication_cta_family_id": cta_family or None,
        "visible_inferred_family_id": visible_family or None,
        "visible_text_inferred_family_id": visible_text_family or None,
        "visible_contract_family_id": visible_contract_family or None,
        "observed_family_ids": observed,
        "missing_roles": missing_roles,
        "mismatched_roles": mismatched_roles,
        "passes_contract": bool(observed) and not missing_roles and not mismatched_roles,
    }


def _post_apply_target_band_contract(
    *,
    family: str,
    visual_snapshot: dict[str, Any],
    publication_probe: dict[str, Any],
) -> dict[str, Any]:
    target_low, target_high = get_target_utilisation_band("balanced")
    domains = _target_domains_for_family(family)
    utils = _summary_domain_utils(visual_snapshot)
    visible_util = _visible_design_guide_utilisation(visual_snapshot)
    if visible_util is not None:
        for domain in domains:
            if utils.get(domain) is None:
                utils[domain] = visible_util
    design_guide_text = str(_safe_dict(visual_snapshot.get("design_guide")).get("text_sample") or "")
    claims_target_band_achieved = bool(
        re.search(r"target band achieved|inside the target band", design_guide_text, re.IGNORECASE)
    )
    domain_rows: list[dict[str, Any]] = []
    low_or_high_outside: list[dict[str, Any]] = []
    for domain in domains:
        util = utils.get(domain)
        row = {
            "domain": domain,
            "utilisation": util,
            "target_low": target_low,
            "target_high": target_high,
            "in_target_band": (
                util is not None
                and float(target_low) - TARGET_BAND_EPS <= float(util) <= float(target_high) + TARGET_BAND_EPS
            ),
            "not_applicable": util is None,
        }
        if util is not None and not row["in_target_band"]:
            low_or_high_outside.append(row)
        domain_rows.append(row)
    blocker_proven = _publication_has_target_band_blocker(
        publication_probe=publication_probe,
        visual_snapshot=visual_snapshot,
    )
    false_target_band_claim = bool(claims_target_band_achieved and low_or_high_outside)
    return {
        "family": family,
        "domains_checked": list(domains),
        "target_low": target_low,
        "target_high": target_high,
        "visible_design_guide_utilisation": visible_util,
        "claims_target_band_achieved": claims_target_band_achieved,
        "false_target_band_claim": false_target_band_claim,
        "summary_domain_utils": utils,
        "domain_results": domain_rows,
        "outside_target_band": low_or_high_outside,
        "blocker_or_exhaustion_proof_present": blocker_proven,
        "passes_contract": bool(not false_target_band_claim and (not low_or_high_outside or blocker_proven)),
    }


def _browser_recipe_from_state(browser_state: dict[str, Any]) -> str:
    browser_probe = _safe_dict(browser_state.get("browser_shared_probe"))
    summary_probe = _safe_dict(browser_state.get("summary_state_probe"))
    return str(
        browser_state.get("browser_recipe")
        or browser_probe.get("browser_recipe")
        or summary_probe.get("browser_recipe")
        or ""
    ).strip()


def _browser_recipe_error_from_state(browser_state: dict[str, Any]) -> str:
    browser_probe = _safe_dict(browser_state.get("browser_shared_probe"))
    summary_probe = _safe_dict(browser_state.get("summary_state_probe"))
    return str(
        browser_state.get("browser_recipe_error")
        or browser_probe.get("browser_recipe_error")
        or summary_probe.get("browser_recipe_error")
        or ""
    ).strip()


def _latest_run_end_after_click(
    start_time_ms: int,
    *,
    expected_updates: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not TRACER_PATH.exists():
        return None
    latest: dict[str, Any] | None = None
    try:
        lines = TRACER_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return None
    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if payload.get("event") != "run_end":
            continue
        try:
            if int(payload.get("timestamp_ms")) < int(start_time_ms):
                continue
        except Exception:
            continue
        if expected_updates:
            run_data = _safe_dict(payload.get("data"))
            route = _safe_dict(run_data.get("last_apply_route"))
            applied = _safe_dict(
                route.get("applied_updates")
                or run_data.get("final_updates")
            )
            if not all(
                key in applied
                and _apply_update_value_matches(applied.get(key), value)
                for key, value in expected_updates.items()
            ):
                continue
        latest = payload
    return latest


def _action_button_probe(page) -> dict[str, Any]:
    buttons: list[dict[str, Any]] = []
    try:
        locator = page.get_by_role("button")
        for index in range(min(locator.count(), 80)):
            button = locator.nth(index)
            try:
                text = " ".join(str(button.inner_text(timeout=750) or "").split())
            except Exception:
                text = ""
            if not text:
                continue
            candidate = any(token.lower() in text.lower() for token in LIVE_ACTION_BUTTON_TEXTS)
            if not candidate:
                continue
            try:
                visible = bool(button.is_visible())
            except Exception:
                visible = False
            try:
                enabled = bool(button.is_enabled())
            except Exception:
                enabled = False
            buttons.append(
                {
                    "index": index,
                    "text": text,
                    "visible": visible,
                    "enabled": enabled,
                }
            )
    except Exception as exc:
        return {"buttons": [], "error": f"{type(exc).__name__}: {exc}"}
    return {
        "buttons": buttons,
        "enabled_action_count": sum(1 for button in buttons if button.get("visible") and button.get("enabled")),
        "visible_action_count": sum(1 for button in buttons if button.get("visible")),
    }


def _click_first_enabled_action(page) -> dict[str, Any]:
    # The Design Guide may rerun once after the final-card probe has settled.
    # Re-query for a bounded window so a probe/click race is recorded as a
    # real click failure only after the live button has had time to reappear.
    deadline = time.time() + 5.0
    attempts = 0
    last_probe: dict[str, Any] = {}
    while time.time() < deadline:
        attempts += 1
        last_probe = _action_button_probe(page)
        locator = page.get_by_role("button")
        for index in range(min(locator.count(), 80)):
            button = locator.nth(index)
            try:
                text = " ".join(str(button.inner_text(timeout=750) or "").split())
            except Exception:
                continue
            if not any(token.lower() in text.lower() for token in LIVE_ACTION_BUTTON_TEXTS):
                continue
            try:
                if not button.is_visible() or not button.is_enabled():
                    continue
                button.click(timeout=10_000)
                return {
                    "clicked": True,
                    "button_index": index,
                    "button_text": text,
                    "requery_attempts": attempts,
                    "probe_click_race_recovered": attempts > 1,
                }
            except PlaywrightTimeoutError as exc:
                return {"clicked": False, "button_index": index, "button_text": text, "error": f"timeout:{exc}", "requery_attempts": attempts}
            except Exception as exc:
                last_probe = {"error": f"{type(exc).__name__}: {exc}"}
                continue
        time.sleep(0.2)
    return {
        "clicked": False,
        "reason": "no_enabled_action_button",
        "requery_attempts": attempts,
        "last_action_probe": last_probe,
        "probe_click_race": True,
    }


def _post_apply_green_pass_visual_contract(snapshot: dict[str, Any]) -> dict[str, Any]:
    design_guide = dict(snapshot.get("design_guide") or {})
    checks = dict(snapshot.get("checks") or {})
    text = str(design_guide.get("text_sample") or "")
    statuses = {
        str(status or "").strip().upper().replace(" ", "_")
        for status in list(checks.get("design_guide_statuses") or [])
        if str(status or "").strip()
    }
    pass_visible = bool(
        "PASS" in statuses
        or re.search(r"Design is efficient|All checks pass|Design accepted", text, re.I)
    )
    blocked_visible = bool(
        re.search(
            r"PREVIEW_BLOCKED|cleanup blocked|repair blocked|blocker proof incomplete|family contract violation",
            text,
            re.I,
        )
    )
    pending_shell_visible = bool(
        re.search(
            r"Checking design guidance|Reviewing strength, detailing, serviceability, and cleanup options",
            text,
            re.I,
        )
    )
    raw_status_visible = bool(re.search(r"(?m)^\s*Status\s*$", text))
    return {
        "pass_visible": pass_visible,
        "blocked_visible": blocked_visible,
        "pending_shell_visible": pending_shell_visible,
        "raw_status_visible": raw_status_visible,
        "design_guide_statuses": sorted(statuses),
        "text_sample": text[:700],
        "passes_contract": bool(
            pass_visible
            and not blocked_visible
            and not pending_shell_visible
            and not raw_status_visible
        ),
    }


def _run_live_family_audit(
    *,
    family: str,
    scenarios: list[dict[str, Any]],
    recipe: str,
    visual_root: Path,
    base_url: str | None,
    port: int,
    headed: bool,
    card_timeout_s: float,
    apply_timeout_s: float,
    executable_action_required: bool = True,
) -> dict[str, Any]:
    visual_root.mkdir(parents=True, exist_ok=True)
    process: subprocess.Popen | None = None
    started_process = False
    errors: list[str] = []
    live_rows: list[dict[str, Any]] = []
    # Keep the live verifier bounded. A page navigation that never reaches a
    # settled Streamlit document must become scenario evidence, not hold the
    # whole release gate open until its outer shell kills the process.
    scenario_budget_s = max(
        20.0,
        float(os.environ.get("DESIGN_BRAIN_LIVE_SCENARIO_BUDGET_S") or 60.0),
    )
    audit_deadline = time.monotonic() + min(
        scenario_budget_s * max(1, len(scenarios)),
        float(os.environ.get("DESIGN_BRAIN_LIVE_AUDIT_DEADLINE_S") or 600.0),
    )
    url_base = base_url or f"http://127.0.0.1:{port}"
    try:
        if base_url:
            _wait_for_http(url_base)
        else:
            before_env = dict(os.environ)
            os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
            try:
                process = _start_streamlit(port)
                started_process = True
            finally:
                os.environ.clear()
                os.environ.update(before_env)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not headed)
            try:
                for scenario in scenarios:
                    scenario_id = str(scenario.get("scenario_id") or f"{family}_LIVE")
                    scenario_recipe = str(scenario.get("browser_recipe") or recipe or "").strip()
                    print(f"[family-live] {family} {scenario_id} recipe={scenario_recipe}", flush=True)
                    row: dict[str, Any] = {
                        "scenario_id": scenario_id,
                        "recipe": scenario_recipe,
                        "family": family,
                        "trigger_passed": bool(scenario.get("trigger_passed")),
                        "failures": [],
                        "observations": [],
                    }
                    if time.monotonic() >= audit_deadline:
                        row["failures"].append("live_audit_deadline_exceeded")
                        row["observations"].append("scenario_not_started_after_bounded_deadline")
                        live_rows.append(row)
                        continue
                    scenario_deadline = min(
                        audit_deadline,
                        time.monotonic() + scenario_budget_s,
                    )
                    try:
                        context = browser.new_context(viewport={"width": 1600, "height": 1100})
                        page = context.new_page()
                        page.set_default_timeout(30_000)
                    except Exception as exc:
                        row["failures"].append(
                            f"browser_context_create_failed:{type(exc).__name__}:{exc}"
                        )
                        live_rows.append(row)
                        continue
                    try:
                        page.goto(
                            _query(
                                url_base,
                                {
                                    "page": "inputs",
                                    "browser_recipe": scenario_recipe,
                                    "browser_test_mode": "1",
                                    "cid": scenario_id,
                            },
                            ),
                            wait_until="domcontentloaded",
                            timeout=max(
                                10_000,
                                int(min(30.0, max(10.0, scenario_budget_s - 5.0)) * 1000),
                            ),
                        )
                        try:
                            page.get_by_label("Browser state").wait_for(state="attached", timeout=12_000)
                        except PlaywrightTimeoutError:
                            row["observations"].append(
                                "browser_state_probe_not_attached; continuing with visible card/apply/tracer evidence"
                            )
                        final_card_probe = _wait_for_final_design_guide_card(page, timeout_s=card_timeout_s)
                        screenshot_before = visual_root / f"{scenario_id}_before_{_datetime_stamp()}.png"
                        visual_snapshot = _capture_visual_snapshot(
                            page,
                            scenario_id=scenario_id,
                            screenshot_path=screenshot_before,
                        )
                        before_state = _safe_dict(visual_snapshot.get("browser_state"))
                        button_probe = _action_button_probe(page)
                        applied_recipe = _browser_recipe_from_state(before_state)
                        recipe_error = _browser_recipe_error_from_state(before_state)
                        recipe_match = applied_recipe == scenario_recipe if applied_recipe else None
                        if applied_recipe and not recipe_match:
                            row["failures"].append(
                                f"requested_browser_recipe_mismatch:requested={scenario_recipe}:applied={applied_recipe}"
                            )
                        elif not applied_recipe:
                            row["observations"].append(
                                "browser_recipe_identity_not_exposed_in_capture_payload"
                            )
                        if recipe_error:
                            row["failures"].append(f"browser_recipe_error:{recipe_error}")
                        if not final_card_probe.get("final_card_ready"):
                            row["failures"].append("final_design_guide_card_not_ready")
                        publication_probe_before_click = _extract_publication_probe(before_state)
                        if (
                            not str(publication_probe_before_click.get("outcome_state") or "").strip()
                            and "PASS" in {str(marker or "").strip().upper() for marker in final_card_probe.get("status_markers") or []}
                        ):
                            for _attempt in range(4):
                                page.wait_for_timeout(750)
                                refreshed_state = _safe_dict(_load_browser_state(page))
                                refreshed_probe = _extract_publication_probe(refreshed_state)
                                if str(refreshed_probe.get("outcome_state") or "").strip():
                                    before_state = refreshed_state
                                    visual_snapshot["browser_state"] = refreshed_state
                                    publication_probe_before_click = refreshed_probe
                                    row["observations"].append(
                                        "publication_probe_refreshed_after_visible_pass_card"
                                    )
                                    break
                        explicit_engineering_blocker_before_click = bool(
                            _publication_has_explicit_engineering_blocker(
                                publication_probe_before_click
                            )
                            or _publication_has_target_band_blocker(
                                publication_probe=publication_probe_before_click,
                                visual_snapshot=visual_snapshot,
                            )
                        )
                        publication_cta = _safe_dict(publication_probe_before_click.get("cta"))
                        publication_cta_updates = _safe_dict(publication_cta.get("updates"))
                        publication_cta_action_type = str(publication_cta.get("action_type") or "").strip()
                        publication_cta_contract_blocked = bool(
                            publication_cta.get("target_band_contract_blocked")
                            or publication_cta.get("preview_pass") is False
                        )
                        visible_enabled_actions = int(button_probe.get("enabled_action_count") or 0)
                        if (
                            visible_enabled_actions > 0
                            and (
                                not publication_cta_action_type
                                or not publication_cta_updates
                                or publication_cta_contract_blocked
                            )
                        ):
                            # A visible action card can arrive before the
                            # browser-state publication payload is refreshed.
                            # Wait for the executable CTA instead of clicking
                            # the generic button against stale state.
                            for _attempt in range(8):
                                page.wait_for_timeout(750)
                                refreshed_state = _safe_dict(_load_browser_state(page))
                                refreshed_probe = _extract_publication_probe(refreshed_state)
                                refreshed_cta = _safe_dict(refreshed_probe.get("cta"))
                                refreshed_updates = _safe_dict(refreshed_cta.get("updates"))
                                refreshed_action_type = str(refreshed_cta.get("action_type") or "").strip()
                                refreshed_blocked = bool(
                                    refreshed_cta.get("target_band_contract_blocked")
                                    or refreshed_cta.get("preview_pass") is False
                                )
                                if refreshed_action_type and refreshed_updates and not refreshed_blocked:
                                    before_state = refreshed_state
                                    visual_snapshot["browser_state"] = refreshed_state
                                    publication_probe_before_click = refreshed_probe
                                    publication_cta = refreshed_cta
                                    publication_cta_updates = refreshed_updates
                                    publication_cta_action_type = refreshed_action_type
                                    publication_cta_contract_blocked = refreshed_blocked
                                    row["observations"].append(
                                        "publication_probe_refreshed_after_visible_action_card"
                                    )
                                    break
                        action_contract_missing = bool(
                            visible_enabled_actions > 0
                            and (
                                not publication_cta_action_type
                                or not publication_cta_updates
                                or publication_cta_contract_blocked
                            )
                            and not explicit_engineering_blocker_before_click
                        )
                        browser_family_contract = _browser_family_identity_contract(
                            family=family,
                            publication_probe=publication_probe_before_click,
                            final_card_probe=final_card_probe,
                            visual_snapshot=visual_snapshot,
                        )
                        if not browser_family_contract.get("passes_contract"):
                            row["failures"].append(
                                "live_browser_family_mismatch:"
                                + json.dumps(browser_family_contract, sort_keys=True)
                            )
                        row.update(
                            {
                                "final_card_probe": final_card_probe,
                                "visual_snapshot_hash": visual_snapshot.get("scenario_hash"),
                                "visual_checks": visual_snapshot.get("checks"),
                                "screenshot_before": str(screenshot_before),
                                "publication_probe_before": publication_probe_before_click,
                                "browser_family_identity_contract": browser_family_contract,
                                "browser_recipe_probe": {
                                    "requested": scenario_recipe,
                                    "applied": applied_recipe,
                                    "error": recipe_error,
                                },
                                "button_probe_before": button_probe,
                                "browser_live_mode": "attached" if base_url else "started_streamlit",
                            }
                        )
                        if (
                            visible_enabled_actions > 0
                            and (
                                not publication_cta_action_type
                                or not publication_cta_updates
                                or publication_cta_contract_blocked
                            )
                        ):
                            row["failures"].append(
                                "visible_apply_button_without_publication_cta_intent:"
                                + json.dumps(
                                    {
                                        "publication_cta_action_type": publication_cta_action_type,
                                        "publication_cta_updates": publication_cta_updates,
                                        "publication_cta_contract_blocked": publication_cta_contract_blocked,
                                        "visible_enabled_actions": visible_enabled_actions,
                                    },
                                    sort_keys=True,
                                )
                            )
                        if (
                            executable_action_required
                            and not button_probe.get("enabled_action_count")
                            and not explicit_engineering_blocker_before_click
                        ):
                            row["failures"].append("no_enabled_action_button")
                        tracer_offset = TRACER_PATH.stat().st_size if TRACER_PATH.exists() else 0
                        click_started_ms = int(time.time() * 1000)
                        click_result = (
                            {
                                "clicked": False,
                                "reason": "publication_cta_not_ready",
                            }
                            if action_contract_missing
                            else _click_first_enabled_action(page)
                        )
                        after_state = before_state
                        run_end_event = None
                        solver_state_timeout = False
                        authoritative_post_apply_settled = False
                        if click_result.get("clicked"):
                            run_end_event, _ = _wait_for_run_end(
                                tracer_offset,
                                timeout_s=max(3.0, apply_timeout_s),
                                start_time_ms=click_started_ms,
                                expected_updates=publication_cta_updates,
                            )
                            if run_end_event is None:
                                run_end_event = _latest_run_end_after_click(
                                    click_started_ms,
                                    expected_updates=publication_cta_updates,
                                )
                            typed_apply_commit_proven = _typed_apply_commit_proven(
                                run_end_event
                            )
                            if typed_apply_commit_proven:
                                typed_run_data = _safe_dict(
                                    _safe_dict(run_end_event).get("data")
                                )
                                typed_route = _safe_dict(
                                    typed_run_data.get("last_apply_route")
                                )
                                typed_applied_updates = _safe_dict(
                                    typed_route.get("applied_updates")
                                )
                                (
                                    after_state,
                                    post_apply_settle_proof,
                                ) = _wait_for_authoritative_post_apply_state(
                                    page,
                                    before_state=before_state,
                                    applied_updates=typed_applied_updates,
                                    timeout_s=max(3.0, apply_timeout_s),
                                )
                                row["post_apply_authoritative_settle_proof"] = (
                                    post_apply_settle_proof
                                )
                                authoritative_post_apply_settled = bool(
                                    post_apply_settle_proof.get("settled")
                                )
                                solver_state_timeout = (
                                    not authoritative_post_apply_settled
                                )
                                if authoritative_post_apply_settled:
                                    row["observations"].append(
                                        "typed_apply_commit_followed_by_authoritative_post_apply_transaction"
                                    )
                                else:
                                    row["failures"].append(
                                        "post_apply_authoritative_state_not_settled"
                                    )
                            else:
                                after_state, solver_state_timeout = _wait_for_solver_state(
                                    page,
                                    timeout_ms=int(max(3.0, apply_timeout_s) * 1000),
                                )
                                if solver_state_timeout:
                                    row["failures"].append(
                                        "post_apply_solver_state_timeout"
                                    )
                                if run_end_event is None:
                                    run_end_event, _ = _wait_for_run_end(
                                        tracer_offset,
                                        timeout_s=max(3.0, apply_timeout_s),
                                        start_time_ms=click_started_ms,
                                        expected_updates=publication_cta_updates,
                                    )
                                    if run_end_event is None:
                                        run_end_event = _latest_run_end_after_click(
                                            click_started_ms,
                                            expected_updates=publication_cta_updates,
                                        )
                            run_data = _safe_dict(_safe_dict(run_end_event).get("data"))
                            statuses = _safe_dict(run_data.get("post_commit_live_statuses"))
                            if run_end_event is None:
                                row["failures"].append("apply_run_end_event_missing")
                            elif str(run_data.get("status") or "").lower() != "pass":
                                row["failures"].append(
                                    f"apply_run_end_status_not_pass:{run_data.get('status')}"
                                )
                            if (
                                run_end_event is not None
                                and run_data.get("all_key_pass") is not True
                                and not typed_apply_commit_proven
                            ):
                                row["failures"].append(
                                    f"post_apply_not_all_key_pass:statuses={statuses}"
                                )
                            if (
                                solver_state_timeout
                                and run_end_event is not None
                                and str(run_data.get("status") or "").lower() == "pass"
                                and (
                                    (
                                        run_data.get("all_key_pass") is True
                                        and not typed_apply_commit_proven
                                    )
                                    or authoritative_post_apply_settled
                                )
                            ):
                                row["failures"] = [
                                    failure
                                    for failure in row["failures"]
                                    if failure != "post_apply_solver_state_timeout"
                                ]
                                row["observations"].append(
                                    "solver_state_probe_timeout_overridden_by_passing_run_end"
                                )
                            try:
                                final_worst = float(run_data.get("final_live_worst_util"))
                            except Exception:
                                final_worst = None
                            if final_worst is not None and final_worst > 1.0:
                                row["failures"].append(
                                    f"post_apply_final_util_above_limit:{final_worst}"
                                )
                            last_apply_route = _safe_dict(run_data.get("last_apply_route"))
                            applied_updates = _safe_dict(
                                last_apply_route.get("applied_updates")
                                or last_apply_route.get("queued_apply_updates")
                            )
                            apply_route_proves_visible_cta = bool(
                                visible_enabled_actions > 0
                                and applied_updates
                                and last_apply_route.get("apply_used_resolved_candidate_payload") is True
                                and last_apply_route.get("payload_binding_match") is True
                                and last_apply_route.get("payload_update_match") is True
                                and str(run_data.get("status") or "").lower() == "pass"
                                and run_data.get("all_key_pass") is True
                            )
                            if apply_route_proves_visible_cta:
                                before_count = len(row["failures"])
                                row["failures"] = [
                                    failure
                                    for failure in row["failures"]
                                    if not str(failure).startswith(
                                        "visible_apply_button_without_publication_cta_intent:"
                                    )
                                    and not str(failure).startswith(
                                        "post_apply_solver_state_timeout"
                                    )
                                ]
                                if len(row["failures"]) != before_count:
                                    row["observations"].append(
                                        "visible_cta_intent_verified_by_apply_route"
                                    )
                            if (
                                publication_cta_contract_blocked
                                and applied_updates
                                and not publication_cta_updates
                            ):
                                row["failures"].append(
                                    "blocked_publication_candidate_was_still_applied:"
                                    + json.dumps(applied_updates, sort_keys=True)
                                )
                        screenshot_after = visual_root / f"{scenario_id}_after_{_datetime_stamp()}.png"
                        post_apply_visual_snapshot: dict[str, Any] = {}
                        if click_result.get("clicked"):
                            try:
                                run_data = _safe_dict(_safe_dict(run_end_event).get("data"))
                                post_apply_card_probe: dict[str, Any] = {}
                                post_apply_authority_ready = bool(
                                    run_end_event is not None
                                    and run_data.get("all_key_pass") is True
                                    and (
                                        not typed_apply_commit_proven
                                        or authoritative_post_apply_settled
                                    )
                                )
                                if post_apply_authority_ready:
                                    post_apply_card_probe = _wait_for_final_design_guide_card(
                                        page,
                                        timeout_s=card_timeout_s,
                                    )
                                    row["post_apply_final_card_probe"] = dict(post_apply_card_probe)
                                visual_deadline = time.monotonic() + min(
                                    10.0,
                                    max(3.0, float(card_timeout_s)),
                                )
                                while True:
                                    post_apply_visual_snapshot = _capture_visual_snapshot(
                                        page,
                                        scenario_id=f"{scenario_id}_post_apply",
                                        screenshot_path=screenshot_after,
                                    )
                                    green_probe = _post_apply_green_pass_visual_contract(
                                        post_apply_visual_snapshot
                                    )
                                    if not green_probe.get("pending_shell_visible"):
                                        break
                                    if time.monotonic() >= visual_deadline:
                                        break
                                    page.wait_for_timeout(750)
                                if post_apply_authority_ready:
                                    green_contract = _post_apply_green_pass_visual_contract(
                                        post_apply_visual_snapshot
                                    )
                                    target_band_contract = _post_apply_target_band_contract(
                                        family=family,
                                        visual_snapshot=post_apply_visual_snapshot,
                                        publication_probe=_extract_publication_probe(_safe_dict(after_state)),
                                    )
                                    row["post_apply_target_band_contract"] = dict(target_band_contract)
                                    safe_followup_contract = bool(
                                        target_band_contract.get("passes_contract")
                                        and target_band_contract.get("outside_target_band")
                                        and not green_contract.get("blocked_visible")
                                        and not green_contract.get("pending_shell_visible")
                                        and not green_contract.get("raw_status_visible")
                                    )
                                    row["post_apply_safe_followup_contract"] = {
                                        "passes_contract": safe_followup_contract,
                                        "reason": (
                                            "outside_target_band_with_blocker_or_exhaustion_proof"
                                            if safe_followup_contract
                                            else "green_pass_or_contract_failure"
                                        ),
                                    }
                                    if not green_contract.get("pass_visible") and not safe_followup_contract:
                                        row["failures"].append("post_apply_final_card_not_green_pass")
                                    if green_contract.get("blocked_visible"):
                                        row["failures"].append("post_apply_final_card_still_blocked_or_cleanup")
                                    if green_contract.get("pending_shell_visible"):
                                        row["failures"].append("post_apply_pending_shell_visible_with_final_card")
                                    if green_contract.get("raw_status_visible"):
                                        row["failures"].append("post_apply_raw_status_block_visible")
                                    row["post_apply_green_pass_visual_contract"] = dict(green_contract)
                                    if not target_band_contract.get("passes_contract"):
                                        row["failures"].append(
                                            "post_apply_outside_target_band_without_engineering_blocker:"
                                            + json.dumps(
                                                target_band_contract.get("outside_target_band") or [],
                                                sort_keys=True,
                                            )
                                        )
                                elif typed_apply_commit_proven:
                                    row["observations"].append(
                                        "post_apply_card_judgement_skipped_until_authoritative_state_settles"
                                    )
                            except Exception as exc:
                                row["failures"].append(
                                    f"post_apply_visual_capture_failed:{type(exc).__name__}:{exc}"
                                )
                        else:
                            try:
                                page.screenshot(path=str(screenshot_after), full_page=True)
                            except Exception as exc:
                                row["failures"].append(f"after_screenshot_failed:{type(exc).__name__}:{exc}")
                        row.update(
                            {
                                "final_card_probe": final_card_probe,
                                "visual_snapshot_hash": visual_snapshot.get("scenario_hash"),
                                "visual_checks": visual_snapshot.get("checks"),
                                "post_apply_visual_snapshot_hash": post_apply_visual_snapshot.get("scenario_hash"),
                                "post_apply_visual_checks": post_apply_visual_snapshot.get("checks"),
                                "post_apply_browser_state_probe": {
                                    key: _safe_dict(
                                        post_apply_visual_snapshot.get("browser_state")
                                    ).get(key)
                                    for key in (
                                        "browser_shared_probe",
                                        "summary_state_probe",
                                        "summary_overview_probe",
                                        "_inputs_engineering_input_transaction_probe",
                                        "_authoritative_design_result_runtime_probe",
                                        "_typed_inputs_apply_probe",
                                        "_finalize_auto_design_publish_latest",
                                        "_inputs_apply_refresh_cycle_latest",
                                        "_shared_write_audit",
                                        "browser_debug_sources",
                                        "browser_state_candidate_diagnostics",
                                        "final_publication_hashes",
                                    )
                                },
                                "screenshot_before": str(screenshot_before),
                                "screenshot_after": str(screenshot_after),
                                "publication_probe_before": publication_probe_before_click,
                                "publication_probe_after": _extract_publication_probe(_safe_dict(after_state)),
                                "browser_family_identity_contract": browser_family_contract,
                                "browser_recipe_probe": {
                                    "requested": scenario_recipe,
                                    "applied": applied_recipe,
                                    "error": recipe_error,
                                },
                                "button_probe_before": button_probe,
                                "click_result": click_result,
                                "solver_state_timeout": bool(solver_state_timeout),
                                "run_end_event": run_end_event,
                                "browser_live_mode": "attached" if base_url else "started_streamlit",
                            }
                        )
                    except Exception as exc:
                        row["failures"].append(f"capture_exception:{type(exc).__name__}:{exc}")
                    if time.monotonic() >= scenario_deadline and "live_audit_deadline_exceeded" not in row["failures"]:
                        row["failures"].append("live_scenario_budget_exceeded")
                    live_rows.append(row)
                    # A browser-context teardown failure must be recorded on
                    # this scenario, not abort the remaining independent
                    # recipes. The family gate must still fail this row, but
                    # it should collect evidence for all ten scenarios.
                    try:
                        context.close()
                    except Exception as exc:
                        row["failures"].append(
                            f"browser_context_close_failed:{type(exc).__name__}:{exc}"
                        )
            finally:
                browser.close()
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        _terminate_process_tree(process)
    failure_rows = [row for row in live_rows if row.get("failures")]
    executed_recipes = [
        str(row.get("recipe") or "").strip()
        for row in live_rows
        if str(row.get("recipe") or "").strip()
    ]
    return {
        "executed": bool(live_rows),
        "family": family,
        "recipe": recipe,
        "recipes": executed_recipes,
        "unique_recipe_count": len(set(executed_recipes)),
        "base_url": url_base,
        "started_process": started_process,
        "scenario_count": len(live_rows),
        "passed_count": len(live_rows) - len(failure_rows),
        "failed_count": len(failure_rows),
        "rows": live_rows,
        "errors": errors,
        "status": "PASS" if live_rows and not failure_rows and not errors else "FAIL",
    }


def _audit_family(
    family: str,
    seed: int,
    visuals: bool,
    *,
    base_url: str | None = None,
    port: int = 8586,
    headed: bool = False,
    live_card_timeout_s: float = 20.0,
    live_apply_timeout_s: float = 12.0,
) -> dict[str, Any]:
    strategy = family_strategy_for(family)
    contract_paths = _contract_paths_for_family(family)
    lock_verifiers = _matching_family_verifiers(family, "lock")
    regression_files = _matching_family_verifiers(family, "regression")
    trigger_rows = _scenario_trigger_rows(family, seed)
    recipe_matrix_status = _live_recipe_matrix_status(family, len(trigger_rows))
    trigger_rows = _attach_live_recipe_matrix(family, trigger_rows)
    ladder_methods = _strategy_ladder_methods(strategy)
    accepted_family_ids = set(FAMILY_CLASSIFICATION_ALIASES.get(family, (family,)))
    predicate_present = any(alias in FAMILY_PREDICATES for alias in accepted_family_ids)
    live_mapping = dict(LIVE_AUDIT_PROBE_MAPPINGS.get(family) or {})
    visual_probe = ROOT / str(live_mapping.get("visual_probe") or "")
    apply_probe = ROOT / str(live_mapping.get("apply_probe") or "")

    readiness_checks = {
        "chooser_predicate_present": predicate_present,
        "ten_contract_scenarios_trigger_expected_family": all(row["trigger_passed"] for row in trigger_rows),
        "family_strategy_registered": strategy is not None,
        "family_contract_present": bool(contract_paths),
        "family_ladder_or_terminal_runtime_hook_present": bool(ladder_methods),
        "family_lock_verifier_present": bool(lock_verifiers),
        "visual_recipe_mapping_present": bool(live_mapping.get("browser_recipe") and visual_probe.exists()),
        "apply_button_probe_mapping_present": bool(live_mapping.get("browser_recipe") and apply_probe.exists()),
        "ten_distinct_live_browser_recipes_present": (
            recipe_matrix_status["ready"]
            if family in LIVE_EXECUTABLE_FAMILIES
            else True
        ),
    }

    blockers = [key for key, value in readiness_checks.items() if not value]
    ready_for_full_live_audit = not blockers
    visual_root = VISUAL_DIR / family
    visual_paths: list[str] = []
    live_execution: dict[str, Any] = {
        "executed": False,
        "status": "NOT_RUN",
        "reason": "visuals not requested or family not enabled for live execution",
    }
    # Structural blockers must not suppress live evidence for an enabled
    # family. Keep those blockers in the final lock result, but execute the
    # browser recipes so the artifact distinguishes a real product failure
    # from a missing static proof. Only skip when the live route itself has no
    # executable mapping/probe.
    live_route_available = bool(
        family in LIVE_EXECUTABLE_FAMILIES
        and live_mapping.get("browser_recipe")
        and visual_probe.exists()
        and apply_probe.exists()
        and recipe_matrix_status.get("ready")
    )
    if visuals and live_route_available:
        visual_root.mkdir(parents=True, exist_ok=True)
        live_execution = _run_live_family_audit(
            family=family,
            scenarios=trigger_rows,
            recipe=str(live_mapping.get("browser_recipe") or ""),
            visual_root=visual_root,
            base_url=base_url,
            port=port,
            headed=headed,
            card_timeout_s=live_card_timeout_s,
            apply_timeout_s=live_apply_timeout_s,
            executable_action_required=family in LIVE_ACTION_REQUIRED_FAMILIES,
        )
        live_execution["ran_despite_structural_blockers"] = bool(blockers)
        for live_row in live_execution.get("rows") or []:
            for key in ("screenshot_before", "screenshot_after"):
                if live_row.get(key):
                    visual_paths.append(str(live_row[key]))
    elif visuals:
        visual_paths.append("not captured: family is not structurally ready for live visual audit")
        live_execution = {
            "executed": False,
            "status": "NOT_RUN",
            "reason": (
                "live route mapping/probe unavailable"
                if family not in LIVE_EXECUTABLE_FAMILIES
                else "live route mapping/probe unavailable despite structural evidence"
            ),
        }

    live_failures = []
    if live_execution.get("executed"):
        for live_row in live_execution.get("rows") or []:
            for failure in live_row.get("failures") or []:
                live_failures.append(
                    {
                        "type": "LIVE_EXECUTION_FAILURE",
                        "scenario_id": live_row.get("scenario_id"),
                        "blocker": failure,
                        "should_block_lock_status": True,
                    }
                )
        for error in live_execution.get("errors") or []:
            live_failures.append(
                {
                    "type": "LIVE_EXECUTION_ERROR",
                    "scenario_id": "LIVE_EXECUTION",
                    "blocker": error,
                    "should_block_lock_status": True,
                }
            )
    if blockers:
        final_status = "NOT_LOCKED_FAIL"
    elif live_execution.get("executed") and not live_failures:
        final_status = "LOCKED_PASS"
    elif live_execution.get("executed"):
        final_status = "NOT_LOCKED_FAIL"
    else:
        final_status = "LOCKED_WITH_WARNINGS"

    published_result: Any = "not executed: structural readiness gate did not pass" if blockers else {}
    button_action_payload: Any = "not executed: structural readiness gate did not pass" if blockers else {}
    button_apply_result: Any = "not executed: structural readiness gate did not pass" if blockers else {}
    best_candidate_proof: Any = "not executed: structural readiness gate did not pass" if blockers else ""
    if live_execution.get("executed"):
        published_result = [
            {
                "scenario_id": row.get("scenario_id"),
                "publication_probe_before": row.get("publication_probe_before"),
                "publication_probe_after": row.get("publication_probe_after"),
                "visual_snapshot_hash": row.get("visual_snapshot_hash"),
            }
            for row in live_execution.get("rows") or []
        ]
        button_action_payload = [
            {
                "scenario_id": row.get("scenario_id"),
                "button_probe_before": row.get("button_probe_before"),
                "cta_before": _safe_dict(row.get("publication_probe_before")).get("cta"),
            }
            for row in live_execution.get("rows") or []
        ]
        button_apply_result = [
            {
                "scenario_id": row.get("scenario_id"),
                "click_result": row.get("click_result"),
                "solver_state_timeout": row.get("solver_state_timeout"),
                "run_end_event": row.get("run_end_event"),
                "failures": row.get("failures"),
            }
            for row in live_execution.get("rows") or []
        ]
        best_candidate_proof = {
            "source": "browser_live_family_10_fuzz",
            "recipe": live_execution.get("recipe"),
            "recipes": live_execution.get("recipes"),
            "unique_recipe_count": live_execution.get("unique_recipe_count"),
            "scenario_count": live_execution.get("scenario_count"),
            "passed_count": live_execution.get("passed_count"),
            "failed_count": live_execution.get("failed_count"),
        }

    return {
        "family": family,
        "contract_files": [str(path.relative_to(ROOT)) for path in contract_paths],
        "lock_verifiers": [str(path.relative_to(ROOT)) for path in lock_verifiers],
        "regression_files": [str(path.relative_to(ROOT)) for path in regression_files],
        "classification_aliases": sorted(accepted_family_ids),
        "live_audit_probe_mapping": live_mapping,
        "live_audit_recipe_matrix": recipe_matrix_status,
        "strategy_registered": strategy is not None,
        "strategy_type": type(strategy).__name__ if strategy is not None else None,
        "ladder_methods": ladder_methods,
        "scenarios": trigger_rows,
        "readiness_checks": readiness_checks,
        "structural_blockers": blockers,
        "ready_for_full_live_10_fuzz_audit": ready_for_full_live_audit,
        "live_execution": live_execution,
        "ladder_candidates_considered": "not executed: structural readiness gate did not pass" if blockers else [],
        "winning_candidate": None,
        "best_candidate_proof": best_candidate_proof,
        "published_result": published_result,
        "button_action_payload": button_action_payload,
        "button_apply_result": button_apply_result,
        "visual_snapshot_paths": visual_paths,
        "architecture_compliance_result": (
            "not executed: structural readiness gate did not pass"
            if blockers
            else (
                "browser live architecture execution completed"
                if live_execution.get("executed")
                else "ready for architecture compliance execution"
            )
        ),
        "failures_found": [
            {
                "type": "STRUCTURAL_READINESS_BLOCKER",
                "blocker": blocker,
                "should_block_lock_status": True,
            }
            for blocker in blockers
        ]
        + live_failures,
        "regressions_recommended": [
            {
                "family": family,
                "scenario_id": "STRUCTURAL_READINESS",
                "root_cause": blocker,
                "expected_behaviour": "family exposes the hook required by live 10-fuzz audit",
                "actual_behaviour": "hook missing or contract scenario did not trigger expected family",
                "proposed_regression_filename": (
                    f"tools/verification/families/regression_{family.lower()}_10_fuzz_{_normalise(blocker)}.py"
                ),
                "should_block_lock_status": True,
            }
            for blocker in blockers
        ],
        "final_lock_status": final_status,
        "status_note": (
            (
                "full browser/live family audit completed"
                if live_execution.get("executed") and not live_failures
                else (
                    "browser/live family audit found failures"
                    if live_execution.get("executed")
                    else "structural readiness passed; full live ladder/publication/button/visual execution still pending"
                )
            )
            if ready_for_full_live_audit
            else "structural readiness blockers prevent full live execution"
        ),
    }


def _write_family_report(row: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{row['family']}_10_fuzz_audit.md"
    lines = [
        f"# {row['family']} 10-Fuzz Audit",
        "",
        f"Final status: `{row['final_lock_status']}`",
        f"Status note: {row['status_note']}",
        "",
        "## Contract File Used",
        "",
        *([f"- `{contract}`" for contract in row["contract_files"]] or ["- none found"]),
        "",
        "## Structural Readiness",
        "",
        *[f"- `{key}`: `{value}`" for key, value in row["readiness_checks"].items()],
        "",
        "## Live Probe Mapping",
        "",
            *(
                [f"- `{key}`: `{value}`" for key, value in row["live_audit_probe_mapping"].items()]
                or ["- none"]
            ),
            "",
            "## Live Recipe Matrix",
            "",
            f"- `ready`: `{row['live_audit_recipe_matrix'].get('ready')}`",
            f"- `recipe_count`: `{row['live_audit_recipe_matrix'].get('recipe_count')}`",
            f"- `unique_recipe_count`: `{row['live_audit_recipe_matrix'].get('unique_recipe_count')}`",
            f"- `all_recipes_known`: `{row['live_audit_recipe_matrix'].get('all_recipes_known')}`",
            f"- `unknown_recipes`: `{row['live_audit_recipe_matrix'].get('unknown_recipes')}`",
            "",
            "| Index | Browser recipe |",
            "| --- | --- |",
            *[
                f"| {index} | `{recipe}` |"
                for index, recipe in enumerate(row["live_audit_recipe_matrix"].get("recipes") or [], start=1)
            ],
            "",
            "## 10 Scenarios Generated",
            "",
        "| Scenario | Browser recipe | Expected | Actual | Trigger | Reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for scenario in row["scenarios"]:
        lines.append(
            "| `{sid}` | `{recipe}` | `{expected}` | `{actual}` | `{trigger}` | `{reason}` |".format(
                sid=scenario["scenario_id"],
                recipe=scenario.get("browser_recipe") or "",
                expected=scenario["expected_family"],
                actual=scenario["actual_selected_family"],
                trigger="PASS" if scenario["trigger_passed"] else "FAIL",
                reason=str(scenario.get("selection_reason") or "").replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## Ladder Candidates Considered",
            "",
            str(row["ladder_candidates_considered"]),
            "",
            "## Browser Live Execution",
            "",
            str(row.get("live_execution") or {}),
            "",
            "## Winning Candidate",
            "",
            str(row["winning_candidate"]),
            "",
            "## Best Candidate Proof",
            "",
            str(row["best_candidate_proof"]),
            "",
            "## Published Result",
            "",
            str(row["published_result"]),
            "",
            "## Button / Action Payload",
            "",
            str(row["button_action_payload"]),
            "",
            "## Button Apply Result",
            "",
            str(row["button_apply_result"]),
            "",
            "## Visual Snapshot Paths",
            "",
            *([f"- `{item}`" for item in row["visual_snapshot_paths"]] or ["- none captured"]),
            "",
            "## Architecture Compliance Result",
            "",
            str(row["architecture_compliance_result"]),
            "",
            "## Failures Found",
            "",
            *(
                [
                    f"- `{failure['type']}`: `{failure['blocker']}`"
                    for failure in row["failures_found"]
                ]
                or ["- none"]
            ),
            "",
            "## Regressions Recommended",
            "",
            *(
                [
                    "- `{proposed}` for `{root}`".format(
                        proposed=regression["proposed_regression_filename"],
                        root=regression["root_cause"],
                    )
                    for regression in row["regressions_recommended"]
                ]
                or ["- none"]
            ),
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_global_report(snapshot: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / "family_10_fuzz_global_summary.md"
    lines = [
        "# Family 10-Fuzz Global Summary",
        "",
        f"Result: `{snapshot['result']}`",
        "",
        "## Summary",
        "",
        f"- Families audited: `{snapshot['summary']['families_audited']}`",
        f"- Families ready for full live 10-fuzz audit: `{snapshot['summary']['families_ready']}`",
        f"- Families blocked structurally: `{snapshot['summary']['families_blocked']}`",
        f"- Scenarios generated: `{snapshot['summary']['scenarios_generated']}`",
        f"- Scenario trigger passes: `{snapshot['summary']['scenario_trigger_passes']}`",
        f"- Scenario trigger failures: `{snapshot['summary']['scenario_trigger_failures']}`",
        "",
        "## Family Table",
        "",
        "| Family | Trigger passes | Ladder failures | Publication mismatches | Button/action failures | Architecture violations | Final status |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in snapshot["families"]:
        trigger_passes = sum(1 for scenario in row["scenarios"] if scenario["trigger_passed"])
        live_execution = dict(row.get("live_execution") or {})
        publication_status = (
            live_execution.get("status")
            if live_execution.get("executed")
            else ("pending-live" if row["ready_for_full_live_10_fuzz_audit"] else "not-run")
        )
        button_status = publication_status
        lines.append(
            "| `{family}` | {triggers}/10 | {ladder} | {publication} | {button} | {architecture} | `{status}` |".format(
                family=row["family"],
                triggers=trigger_passes,
                ladder=1 if "family_ladder_or_terminal_runtime_hook_present" in row["structural_blockers"] else 0,
                publication=publication_status,
                button=button_status,
                architecture=len(row["structural_blockers"]),
                status=row["final_lock_status"],
            )
        )
    lines.extend(
        [
            "",
            "## Families Ready For Full Live 10-Fuzz Execution",
            "",
            *(
                [f"- `{row['family']}`" for row in snapshot["families"] if row["ready_for_full_live_10_fuzz_audit"]]
                or ["- none"]
            ),
            "",
            "## Families With Completed Live 10-Fuzz Execution",
            "",
            *(
                [
                    f"- `{row['family']}`: `{dict(row.get('live_execution') or {}).get('status')}`"
                    for row in snapshot["families"]
                    if dict(row.get("live_execution") or {}).get("executed")
                ]
                or ["- none"]
            ),
            "",
            "## Families Safe To Keep Locked",
            "",
            *(
                [f"- `{row['family']}`" for row in snapshot["families"] if row["final_lock_status"] == "LOCKED_PASS"]
                or ["- none; this runner has only proven readiness, not full live fuzz completion"]
            ),
            "",
            "## Families That Must Be Unlocked Or Kept Below v2 Lock",
            "",
            *(
                [f"- `{row['family']}`: {', '.join(row['structural_blockers'])}" for row in snapshot["families"] if row["structural_blockers"]]
                or ["- none"]
            ),
            "",
            "## Recommended New Regression Tests",
            "",
        ]
    )
    for row in snapshot["families"]:
        for regression in row["regressions_recommended"]:
            lines.append(
                "- `{family}` `{scenario}` -> `{file}`".format(
                    family=regression["family"],
                    scenario=regression["scenario_id"],
                    file=regression["proposed_regression_filename"],
                )
            )
    lines.extend(
        [
            "",
            "## Stop Decision",
            "",
            "The full live ladder/publication/button/visual audit was not executed because at least one requested family is not structurally ready.",
            "This is intentional: the runner must not fabricate candidate, publication, apply, or screenshot evidence.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_snapshot(snapshot: dict[str, Any]) -> Path:
    VERIFY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    path = VERIFY_DIR / f"family_10_fuzz_audit_{stamp}.json"
    snapshot["artifact"] = str(path)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _selected_families(args: argparse.Namespace) -> list[str]:
    if args.all:
        return list(FAMILIES)
    family = str(args.family or "").strip().upper()
    if family:
        if family not in FAMILIES:
            raise SystemExit(f"Unknown family for 10-fuzz audit: {family}")
        return [family]
    raise SystemExit("Use --all or --family FAMILY_ID")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", help="Audit one family")
    parser.add_argument("--all", action="store_true", help="Audit all requested families")
    parser.add_argument("--visuals", action="store_true", help="Capture visuals when structural readiness passes")
    parser.add_argument("--seed", type=int, default=1007, help="Deterministic seed")
    parser.add_argument("--base-url", default=None, help="Use an already-running app for live family execution")
    parser.add_argument("--port", type=int, default=8586, help="Port for temporary Streamlit live execution server")
    parser.add_argument("--headed", action="store_true", help="Run live browser execution headed")
    parser.add_argument("--live-card-timeout-s", type=float, default=20.0, help="Per-scenario final card wait")
    parser.add_argument("--live-apply-timeout-s", type=float, default=12.0, help="Per-scenario post-click wait")
    args = parser.parse_args(argv)

    families = _selected_families(args)
    rows = [
        _audit_family(
            family,
            args.seed,
            args.visuals,
            base_url=args.base_url,
            port=args.port,
            headed=bool(args.headed),
            live_card_timeout_s=float(args.live_card_timeout_s),
            live_apply_timeout_s=float(args.live_apply_timeout_s),
        )
        for family in families
    ]
    for row in rows:
        row["report"] = str(_write_family_report(row))
    scenarios = [scenario for row in rows for scenario in row["scenarios"]]
    blocked = [row for row in rows if row["structural_blockers"]]
    live_failures = [
        row
        for row in rows
        if dict(row.get("live_execution") or {}).get("executed")
        and dict(row.get("live_execution") or {}).get("status") != "PASS"
    ]
    live_passes = [
        row
        for row in rows
        if dict(row.get("live_execution") or {}).get("executed")
        and dict(row.get("live_execution") or {}).get("status") == "PASS"
    ]
    if blocked:
        result = "STRUCTURAL_NOT_READY"
    elif live_failures:
        result = "LIVE_EXECUTION_FAIL"
    elif live_passes and len(live_passes) == len(rows):
        result = "LIVE_EXECUTION_PASS"
    else:
        result = "READY_FOR_LIVE_EXECUTION"
    snapshot = {
        "schema": "design_brain.family_10_fuzz_audit.v1",
        "result": result,
        "seed": args.seed,
        "visuals_requested": bool(args.visuals),
        "base_url": args.base_url,
        "port": args.port,
        "excluded_non_executable_classification_states": NON_EXECUTABLE_CLASSIFICATION_STATES,
        "families": rows,
        "summary": {
            "families_audited": len(rows),
            "families_ready": sum(1 for row in rows if row["ready_for_full_live_10_fuzz_audit"]),
            "families_blocked": len(blocked),
            "families_live_executed": len(live_passes) + len(live_failures),
            "families_live_passed": len(live_passes),
            "families_live_failed": len(live_failures),
            "scenarios_generated": len(scenarios),
            "scenario_trigger_passes": sum(1 for scenario in scenarios if scenario["trigger_passed"]),
            "scenario_trigger_failures": sum(1 for scenario in scenarios if not scenario["trigger_passed"]),
            "ladder_failures": sum(
                1 for row in rows if "family_ladder_or_terminal_runtime_hook_present" in row["structural_blockers"]
            ),
            "publication_mismatches": sum(
                int(dict(row.get("live_execution") or {}).get("failed_count") or 0) for row in rows
            )
            if live_passes or live_failures
            else "not-run-until-structural-readiness-passes",
            "button_action_failures": sum(
                int(dict(row.get("live_execution") or {}).get("failed_count") or 0) for row in rows
            )
            if live_passes or live_failures
            else "not-run-until-structural-readiness-passes",
            "architecture_violations": sum(len(row["structural_blockers"]) for row in rows),
        },
    }
    snapshot_path = _write_snapshot(snapshot)
    global_report = _write_global_report(snapshot)
    print(f"family 10-fuzz audit {snapshot['result']}")
    print(f"JSON: {snapshot_path}")
    print(f"Global report: {global_report}")
    if blocked:
        print("Stopped before live execution because structural readiness failed.")
        return 2
    if live_failures:
        print("Live execution ran and found failures.")
        return 3
    if live_passes and len(live_passes) == len(rows):
        print("All selected families passed live execution.")
        return 0
    print("All selected families are structurally ready for live execution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
