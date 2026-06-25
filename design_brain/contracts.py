"""Design Brain contract IDs and validation rules.

This module owns pure validation/invariant checks for DesignBrainResult. It
does not generate candidates, evaluate formulas, apply updates, or render UI.
"""

from __future__ import annotations

from typing import Any

from design_brain.candidates import candidate_is_executable
from design_brain.evidence import (
    repair_search_exhaustive,
)
from design_brain.optimisation import (
    exact_stop_evidence_by_family,
    optimisation_search_exhaustive,
)
from design_brain.interface import DesignBrainEvidence, DesignBrainResult


ACCEPTED_UTIL_LOW = 0.85
ACCEPTED_UTIL_HIGH = 1.0


def _as_dict(value: Any) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _truthy_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def bottom_arrangement_to_shared_updates(arrangement: dict) -> dict:
    """Map an explicit bottom reinforcement arrangement to shared update keys."""
    count_1 = int(arrangement.get("bot1_count", 0) or 0)
    count_2 = int(arrangement.get("bot2_count", 0) or 0)
    dia_1 = int(arrangement.get("db_bot_1", 0) or 0)
    dia_2 = int(arrangement.get("db_bot_2", dia_1) or dia_1)
    row_count = 2 if count_2 > 0 else 1
    return {
        "bot1_layout_mode": "Count",
        "bot1_count": count_1,
        "db_bot_1": dia_1,
        "bot2_layout_mode": "Count",
        "bot2_count": count_2,
        "db_bot_2": dia_2,
        "bot_row_count": row_count,
        "bot_row_1_mode": "Count",
        "bot_row_1_bars": count_1,
        "bot_row_1_spacing": 0.0,
        "bot_row_1_dia": dia_1,
        "bot_row_2_mode": "Count",
        "bot_row_2_bars": count_2,
        "bot_row_2_spacing": 0.0,
        "bot_row_2_dia": dia_2,
    }


def resolve_recommendation_payload_fast_path(item: dict | None) -> dict:
    """Return direct recommendation updates from explicit item payload fields."""
    if not isinstance(item, dict):
        return {}
    payload = dict(item.get("action_payload") or {})
    resolved = payload.get("resolved_candidate_updates")
    if isinstance(resolved, dict) and resolved:
        return dict(resolved)
    direct = payload.get("updates")
    if isinstance(direct, dict) and direct:
        return dict(direct)
    return {}


def contract_ids_for_outcome(outcome_id: str, evidence: dict) -> list[str]:
    ids = [
        "design_guide_outcome_contract",
        "design_brain_underdesign_repair_contract",
        "design_brain_target_band_contract",
        "ui_truth_contract",
    ]
    if outcome_id:
        ids.append(outcome_id)
    if _as_dict(evidence).get("selected_candidate_id"):
        ids.append("candidate_integrity")
    if _as_dict(evidence).get("candidate_search_exhaustive") is not None:
        ids.append("verifier_proof_evidence")
    return ids


def _executable_repair_available(result: DesignBrainResult, evidence: dict) -> bool:
    if any(candidate_is_executable(option) for option in result.repair_options):
        return True
    repair_count_keys = (
        "executable_repair_candidate_count",
        "safe_repair_candidate_count",
        "active_fail_safe_executor_count",
        "active_fail_repair_candidate_count",
        "repair_candidate_count",
    )
    if any(_truthy_int(evidence.get(key)) > 0 for key in repair_count_keys):
        return True
    if result.active_failures and result.cta.enabled and result.cta.executor_backed:
        return True
    return False


def _executable_optimisation_available(result: DesignBrainResult, evidence: dict) -> bool:
    if any(candidate_is_executable(option) for option in result.optimisation_options):
        return True
    optimisation_count_keys = (
        "executable_candidate_count",
        "safe_executor_backed_candidates_count",
        "safe_cleanup_count",
        "executable_cleanup_count",
        "safe_local_cleanup_count",
        "target_band_candidate_count",
        "executable_target_band_candidate_count",
    )
    if any(_truthy_int(evidence.get(key)) > 0 for key in optimisation_count_keys):
        return True
    return False


def _has_exact_stop_evidence(evidence: dict) -> bool:
    blockers = exact_stop_evidence_by_family(evidence)
    if not blockers:
        return False
    for blocker in blockers.values():
        if (
            blocker.get("exact_blocker")
            or blocker.get("search_exhaustive")
            or blocker.get("cleanup_search_exhaustive")
            or blocker.get("repair_search_exhaustive")
            or blocker.get("target_band_search_exhaustive")
        ):
            return True
    return False


def _major_family_utils(evidence: dict) -> dict[str, float]:
    sources = (
        _as_dict(evidence.get("overview")).get("utils"),
        evidence.get("utils"),
        evidence.get("family_utils"),
    )
    out: dict[str, float] = {}
    for source in sources:
        for family, value in _as_dict(source).items():
            fam = str(family or "").strip().lower()
            if fam not in {"bending", "shear", "crack", "deflection", "serviceability"}:
                continue
            parsed = _as_float(value)
            if parsed is not None:
                out[fam] = parsed
    family_status_current = _as_dict(evidence.get("family_status_current"))
    for family, row in family_status_current.items():
        fam = str(family or "").strip().lower()
        if fam not in {"bending", "shear", "crack", "deflection", "serviceability"}:
            continue
        parsed = _as_float(_as_dict(row).get("util"))
        if parsed is not None:
            out.setdefault(fam, parsed)
    return out


def _has_major_family_in_accepted_band(evidence: dict) -> bool:
    for value in _major_family_utils(evidence).values():
        if ACCEPTED_UTIL_LOW <= float(value) <= ACCEPTED_UTIL_HIGH:
            return True
    return False


def validate_design_brain_result(result: DesignBrainResult) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    cta = result.cta
    evidence = result.evidence.candidate_search if isinstance(result.evidence, DesignBrainEvidence) else {}
    if cta.enabled and not (cta.executor_backed and cta.action_type and cta.updates):
        failures.append("enabled_cta_without_executor_backed_action")
    if (
        result.card_kind == "ACTION"
        and result.is_terminal
        and not cta.enabled
        and (cta.disabled_reason or "").strip()
    ):
        failures.append("disabled_apply_terminal_action_state")
    if result.is_terminal and result.active_failures and result.outcome_id == "passing_exact_stop":
        failures.append("terminal_pass_with_active_required_failures")
    repair_available = _executable_repair_available(result, evidence)
    optimisation_available = _executable_optimisation_available(result, evidence)
    exact_stop_available = _has_exact_stop_evidence(evidence)
    if result.active_failures:
        if repair_available and not cta.enabled:
            failures.append("underdesign_repair_candidate_not_published")
        if result.is_terminal and repair_available:
            failures.append("terminal_fail_with_available_repair_candidate")
        if result.is_terminal and not repair_available and not repair_search_exhaustive(evidence):
            failures.append("terminal_fail_missing_exhaustive_repair_evidence")
    if not result.active_failures:
        terminal_like = bool(
            result.is_terminal
            or result.outcome_id in {"passing_exact_stop", "blocked_specific_reason"}
            or (result.card_kind in {"PASS", "BLOCKED"} and not cta.enabled)
        )
        if terminal_like and optimisation_available and not cta.enabled:
            failures.append("target_band_optimisation_candidate_not_published")
        if (
            terminal_like
            and not optimisation_available
            and _major_family_utils(evidence)
            and not _has_major_family_in_accepted_band(evidence)
            and not exact_stop_available
        ):
            failures.append("passing_terminal_without_target_band_or_exact_stop")
        if terminal_like and exact_stop_available and not optimisation_search_exhaustive(evidence):
            failures.append("exact_stop_missing_exhaustive_optimisation_evidence")
    safe_combined = result.evidence.safe_combined_cleanup
    if (
        safe_combined.get("safe_cleanup_candidate_found")
        and safe_combined.get("executor_backed")
        and safe_combined.get("preview_pass") is not False
        and not cta.enabled
    ):
        failures.append("safe_combined_cleanup_candidate_visible_cta_disabled")
    if result.card_kind in {"BLOCKED", "PASS"} and cta.enabled:
        failures.append("blocked_or_pass_card_has_enabled_cta")
    fp = result.fingerprint if isinstance(result.fingerprint, dict) else {}
    publication_fp = fp.get("publication")
    debug_fp = fp.get("debug")
    if publication_fp is not None and debug_fp is not None and publication_fp != debug_fp:
        failures.append("result_fingerprint_mismatch")
    return {
        "ok": not failures,
        "failures": failures,
        "warnings": warnings,
    }
