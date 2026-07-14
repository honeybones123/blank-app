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
    _start_streamlit,
    _wait_for_http,
    _wait_for_run_end,
    _wait_for_solver_state,
)


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
        "browser_recipe": "MATRIX_DEFLECTION_ONLY_FAIL",
        "visual_probe": "tools/verification/design_guide_browser_live_visual_consistency_snapshot.py",
        "apply_probe": "tools/verification/families/serviceability_governs_locked_regression.py",
        "expected_apply_surface": "serviceability blocked/exact-stop publication with no family-owned apply CTA",
    },
}

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
            bending_utilisation=1.12 + index * 0.01,
            bending_state="FAIL",
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


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


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
    if enabled_cta_source and not (_truthy(cta_payload.get("enabled")) or _truthy(cta_payload.get("actionable"))):
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
    cards = _safe_dict(snapshot.get("summary_cards"))
    return {
        "bending": _parse_util_float(_safe_dict(cards.get("bending_uls")).get("utilisation")),
        "shear": _parse_util_float(_safe_dict(cards.get("shear_uls")).get("utilisation")),
    }


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


def _post_apply_target_band_contract(
    *,
    family: str,
    visual_snapshot: dict[str, Any],
    publication_probe: dict[str, Any],
) -> dict[str, Any]:
    target_low, target_high = get_target_utilisation_band("balanced")
    domains = _target_domains_for_family(family)
    utils = _summary_domain_utils(visual_snapshot)
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
    return {
        "family": family,
        "domains_checked": list(domains),
        "target_low": target_low,
        "target_high": target_high,
        "summary_domain_utils": utils,
        "domain_results": domain_rows,
        "outside_target_band": low_or_high_outside,
        "blocker_or_exhaustion_proof_present": blocker_proven,
        "passes_contract": bool(not low_or_high_outside or blocker_proven),
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


def _latest_run_end_after_click(start_time_ms: int) -> dict[str, Any] | None:
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
            return {"clicked": True, "button_index": index, "button_text": text}
        except PlaywrightTimeoutError as exc:
            return {"clicked": False, "button_index": index, "button_text": text, "error": f"timeout:{exc}"}
        except Exception as exc:
            return {"clicked": False, "button_index": index, "button_text": text, "error": f"{type(exc).__name__}: {exc}"}
    return {"clicked": False, "reason": "no_enabled_action_button"}


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
        or re.search(r"\bDesign is efficient\b|\bAll checks pass\b|\bDesign accepted\b", text, re.I)
    )
    blocked_visible = bool(
        re.search(
            r"cleanup blocked|repair blocked|blocker proof incomplete|family contract violation",
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
                    print(f"[family-live] {family} {scenario_id} recipe={recipe}", flush=True)
                    context = browser.new_context(viewport={"width": 1600, "height": 1100})
                    page = context.new_page()
                    page.set_default_timeout(30_000)
                    row: dict[str, Any] = {
                        "scenario_id": scenario_id,
                        "recipe": recipe,
                        "family": family,
                        "trigger_passed": bool(scenario.get("trigger_passed")),
                        "failures": [],
                        "observations": [],
                    }
                    try:
                        page.goto(
                            _query(
                                url_base,
                                {
                                    "page": "inputs",
                                    "browser_recipe": recipe,
                                    "browser_test_mode": "1",
                                    "cid": scenario_id,
                                },
                            ),
                            wait_until="domcontentloaded",
                            timeout=90_000,
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
                        recipe_match = applied_recipe == recipe if applied_recipe else None
                        if applied_recipe and not recipe_match:
                            row["failures"].append(
                                f"requested_browser_recipe_mismatch:requested={recipe}:applied={applied_recipe}"
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
                        if (
                            executable_action_required
                            and not button_probe.get("enabled_action_count")
                            and not explicit_engineering_blocker_before_click
                        ):
                            row["failures"].append("no_enabled_action_button")
                        tracer_offset = TRACER_PATH.stat().st_size if TRACER_PATH.exists() else 0
                        click_started_ms = int(time.time() * 1000)
                        click_result = _click_first_enabled_action(page)
                        after_state = before_state
                        run_end_event = None
                        solver_state_timeout = False
                        if click_result.get("clicked"):
                            after_state, solver_state_timeout = _wait_for_solver_state(
                                page,
                                timeout_ms=int(max(3.0, apply_timeout_s) * 1000),
                            )
                            run_end_event, _ = _wait_for_run_end(
                                tracer_offset,
                                timeout_s=max(3.0, apply_timeout_s),
                                start_time_ms=click_started_ms,
                            )
                            if run_end_event is None:
                                run_end_event = _latest_run_end_after_click(click_started_ms)
                            run_data = _safe_dict(_safe_dict(run_end_event).get("data"))
                            statuses = _safe_dict(run_data.get("post_commit_live_statuses"))
                            if run_end_event is None:
                                row["failures"].append("apply_run_end_event_missing")
                            elif str(run_data.get("status") or "").lower() != "pass":
                                row["failures"].append(
                                    f"apply_run_end_status_not_pass:{run_data.get('status')}"
                                )
                            if run_end_event is not None and run_data.get("all_key_pass") is not True:
                                row["failures"].append(
                                    f"post_apply_not_all_key_pass:statuses={statuses}"
                                )
                            try:
                                final_worst = float(run_data.get("final_live_worst_util"))
                            except Exception:
                                final_worst = None
                            if final_worst is not None and final_worst > 1.0:
                                row["failures"].append(
                                    f"post_apply_final_util_above_limit:{final_worst}"
                                )
                        screenshot_after = visual_root / f"{scenario_id}_after_{_datetime_stamp()}.png"
                        post_apply_visual_snapshot: dict[str, Any] = {}
                        if click_result.get("clicked"):
                            try:
                                run_data = _safe_dict(_safe_dict(run_end_event).get("data"))
                                post_apply_card_probe: dict[str, Any] = {}
                                if run_end_event is not None and run_data.get("all_key_pass") is True:
                                    post_apply_card_probe = _wait_for_final_design_guide_card(
                                        page,
                                        timeout_s=card_timeout_s,
                                    )
                                    row["post_apply_final_card_probe"] = dict(post_apply_card_probe)
                                post_apply_visual_snapshot = _capture_visual_snapshot(
                                    page,
                                    scenario_id=f"{scenario_id}_post_apply",
                                    screenshot_path=screenshot_after,
                                )
                                if run_end_event is not None and run_data.get("all_key_pass") is True:
                                    green_contract = _post_apply_green_pass_visual_contract(
                                        post_apply_visual_snapshot
                                    )
                                    if not green_contract.get("pass_visible"):
                                        row["failures"].append("post_apply_final_card_not_green_pass")
                                    if green_contract.get("blocked_visible"):
                                        row["failures"].append("post_apply_final_card_still_blocked_or_cleanup")
                                    if green_contract.get("pending_shell_visible"):
                                        row["failures"].append("post_apply_pending_shell_visible_with_final_card")
                                    if green_contract.get("raw_status_visible"):
                                        row["failures"].append("post_apply_raw_status_block_visible")
                                    row["post_apply_green_pass_visual_contract"] = dict(green_contract)
                                    target_band_contract = _post_apply_target_band_contract(
                                        family=family,
                                        visual_snapshot=post_apply_visual_snapshot,
                                        publication_probe=_extract_publication_probe(_safe_dict(after_state)),
                                    )
                                    row["post_apply_target_band_contract"] = dict(target_band_contract)
                                    if not target_band_contract.get("passes_contract"):
                                        row["failures"].append(
                                            "post_apply_outside_target_band_without_engineering_blocker:"
                                            + json.dumps(
                                                target_band_contract.get("outside_target_band") or [],
                                                sort_keys=True,
                                            )
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
                                "screenshot_before": str(screenshot_before),
                                "screenshot_after": str(screenshot_after),
                                "publication_probe_before": publication_probe_before_click,
                                "publication_probe_after": _extract_publication_probe(_safe_dict(after_state)),
                                "browser_recipe_probe": {
                                    "requested": recipe,
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
                    live_rows.append(row)
                    context.close()
            finally:
                browser.close()
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()
    failure_rows = [row for row in live_rows if row.get("failures")]
    return {
        "executed": bool(live_rows),
        "family": family,
        "recipe": recipe,
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
    if visuals and ready_for_full_live_audit:
        visual_root.mkdir(parents=True, exist_ok=True)
        if family in LIVE_EXECUTABLE_FAMILIES:
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
            for live_row in live_execution.get("rows") or []:
                for key in ("screenshot_before", "screenshot_after"):
                    if live_row.get(key):
                        visual_paths.append(str(live_row[key]))
        else:
            live_execution = {
                "executed": False,
                "status": "NOT_RUN",
                "reason": "family is structurally ready but live execution is not enabled for this family in this slice",
            }
    elif visuals:
        visual_paths.append("not captured: family is not structurally ready for live visual audit")
        live_execution = {
            "executed": False,
            "status": "NOT_RUN",
            "reason": "structural readiness gate did not pass",
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
        "## 10 Scenarios Generated",
        "",
        "| Scenario | Expected | Actual | Trigger | Reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for scenario in row["scenarios"]:
        lines.append(
            "| `{sid}` | `{expected}` | `{actual}` | `{trigger}` | `{reason}` |".format(
                sid=scenario["scenario_id"],
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
