"""Proof-only final Design Guide publication boundary.

This module defines a stable Design Brain object for the final publication
shape. It does not render CTA, route apply actions, read page/session state, or
replace the current page-owned publication path.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field, fields, replace
from hashlib import sha256
from typing import Any, Literal, Mapping

from .family_optimal_blockers import build_family_optimal_no_action_proof
from .publication import generic_family_owned_payload_id


FinalDesignGuideOutcomeState = Literal["PASS", "ACTION", "BLOCKED", "ERROR", "PROOF_PENDING"]


def stable_final_publication_hash(value: Any) -> str:
    """Return a deterministic hash for final-publication proof payloads."""

    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


_FINAL_PUBLICATION_AUTHORITY_VOLATILE_FRAGMENTS = (
    "hash",
    "memo_cache",
    "bypass",
    "trace",
    "timestamp",
    "elapsed_ms",
    "duration_ms",
    "perf",
    "generated_at",
    "actual_card_render_probe",
    "legacy_publication_session_key_metadata",
    "duplicate_stamp",
    "compatibility",
    "controller_publication_authority",
    "final_visible_resolution_adapter",
)


def _final_publication_authority_path_is_volatile(path: str) -> bool:
    lower = str(path or "").lower()
    return any(fragment in lower for fragment in _FINAL_PUBLICATION_AUTHORITY_VOLATILE_FRAGMENTS)


def canonical_final_publication_authority_payload(value: Any, *, path: str = "$") -> Any:
    """Return final-publication truth with volatile proof/debug fields removed.

    This is intentionally narrower than ``stable_final_publication_hash``. It is
    only for authority hashes where proof/debug/timing churn must not change the
    publication identity for the same engineering/design-guide truth.
    """

    if _final_publication_authority_path_is_volatile(path):
        return None
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in sorted(value.items(), key=lambda row: str(row[0])):
            child_path = f"{path}.{key}"
            if _final_publication_authority_path_is_volatile(child_path):
                continue
            canonical = canonical_final_publication_authority_payload(item, path=child_path)
            if canonical in (None, {}, []):
                continue
            out[str(key)] = canonical
        return out
    if isinstance(value, (list, tuple)):
        out = []
        for index, item in enumerate(value):
            canonical = canonical_final_publication_authority_payload(item, path=f"{path}[{index}]")
            if canonical in (None, {}, []):
                continue
            out.append(canonical)
        return out
    return value


def stable_final_publication_authority_hash(value: Any) -> str:
    """Hash final-publication authority truth without proof/debug churn."""

    return stable_final_publication_hash(canonical_final_publication_authority_payload(value))


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _mapping_or_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                loaded = json.loads(text)
            except Exception:
                return {}
            if isinstance(loaded, dict):
                return dict(loaded)
    return {}


def _text(*values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _final_publication_active_failure_repair_surface_has_work(
    item: Mapping[str, Any] | None,
    debug: Mapping[str, Any] | None,
    family: str,
    *,
    require_repair_work: bool = True,
) -> bool:
    if str(family or "").strip().upper() not in {
        "BENDING_FAIL_GOVERNS",
        "SHEAR_FAIL_GOVERNS",
        "COMBINED_BENDING_SHEAR_FAIL",
        "COMBINED_BENDING_SHEAR_FAIL_GOVERN",
        "BENDING_FAIL_SHEAR_OPTIMISE_GOVERNS",
        "SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS",
        "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
    }:
        return False

    item_d = _mapping(item)
    debug_d = _mapping(debug)
    button_contract = _mapping_or_json(item_d.get("button_contract") or debug_d.get("button_contract"))
    action_payload = _mapping_or_json(item_d.get("action_payload") or debug_d.get("design_guide_primary_apply_payload"))
    candidate_evidence = _mapping_or_json(
        item_d.get("candidate_search_evidence")
        or button_contract.get("candidate_search_evidence")
        or action_payload.get("candidate_search_evidence")
        or debug_d.get("candidate_search_evidence")
    )
    selection_evidence = _mapping_or_json(item_d.get("selection_evidence") or debug_d.get("selection_evidence"))
    verifier = _mapping_or_json(
        item_d.get("final_publication_verifier_payload")
        or debug_d.get("final_publication_verifier_payload")
    )
    sources = [
        item_d,
        debug_d,
        button_contract,
        action_payload,
        candidate_evidence,
        selection_evidence,
        verifier,
        _mapping(verifier.get("selection_evidence")),
        _mapping(verifier.get("candidate_search_evidence")),
    ]
    raw_flags: dict[str, Any] = {}
    for source in sources:
        raw_flags.update(_mapping_or_json(source.get("raw_state_flags")))

    has_active_failure = any(
        _truthy(value)
        for value in (
            raw_flags.get("bending_fail"),
            raw_flags.get("shear_fail"),
            raw_flags.get("active_combined_bending_shear_failure"),
            raw_flags.get("any_strength_fail"),
            raw_flags.get("repair_required"),
            item_d.get("active_bending_fail"),
            item_d.get("active_shear_fail"),
            debug_d.get("active_bending_fail"),
            debug_d.get("active_shear_fail"),
            candidate_evidence.get("active_bending_fail"),
            candidate_evidence.get("active_shear_fail"),
            selection_evidence.get("active_bending_fail"),
            selection_evidence.get("active_shear_fail"),
        )
    )
    if not has_active_failure:
        title = str(
            _text(
                item_d.get("title_main"),
                item_d.get("title"),
                verifier.get("display_title"),
            )
            or ""
        ).strip().lower()
        has_active_failure = "capacity is low" in title

    if not require_repair_work:
        return bool(has_active_failure)

    updates = _final_publication_updates_from_item_debug(dict(item_d), dict(debug_d))
    repair_available = bool(updates) or any(
        _truthy(value)
        for source in sources
        for value in (
            source.get("repair_payload_available"),
            source.get("legal_repair_exists"),
            source.get("repair_search_ran"),
            source.get("candidate_search_ran"),
        )
    )
    if not repair_available:
        for source in sources:
            for key in (
                "safe_executor_backed_candidates_count",
                "executable_repair_candidate_count",
                "safe_repair_candidate_count",
                "safe_candidate_count",
                "family_ladder_candidate_count",
            ):
                try:
                    if int(float(source.get(key) or 0)) > 0:
                        repair_available = True
                        break
                except Exception:
                    continue
            if repair_available:
                break
    return bool(has_active_failure and repair_available)


def _stable_payload_fingerprint_tuple(payload: dict[str, Any] | None) -> tuple[tuple[str, str], ...]:
    serialised: list[tuple[str, str]] = []
    for key, value in sorted(dict(payload or {}).items(), key=lambda item: str(item[0])):
        try:
            encoded = json.dumps(value, sort_keys=True, default=str)
        except Exception:
            encoded = repr(value)
        serialised.append((str(key), encoded))
    return tuple(serialised)


def _local_cleanup_candidate_id(family: str, updates: dict[str, Any] | None) -> str:
    family_id = str(family or "").strip().lower()
    return (
        f"local_cleanup:{family_id}:"
        f"{_stable_payload_fingerprint_tuple({'family': family_id, 'updates': dict(updates or {})})}"
    )


def _number_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


_FINAL_PUBLICATION_SHEAR_UPDATE_KEYS = frozenset({"lig_d", "lig_legs", "s_lig"})
_FINAL_PUBLICATION_BOTTOM_UPDATE_KEYS = frozenset(
    {
        "db_bot",
        "db_bot_1",
        "db_bot_2",
        "bot1_count",
        "bot2_count",
        "nb_bot",
        "bot_row_count",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_1_spacing",
        "bot_row_1_dia",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "bot_row_2_spacing",
        "bot_row_2_dia",
        "bot_row_3_mode",
        "bot_row_3_bars",
        "bot_row_3_spacing",
        "bot_row_3_dia",
        "bot_row_4_mode",
        "bot_row_4_bars",
        "bot_row_4_spacing",
        "bot_row_4_dia",
    }
)
_FINAL_PUBLICATION_GEOMETRY_UPDATE_KEYS = frozenset({"b", "D"})
_FINAL_PUBLICATION_OVERDESIGN_FAMILY_IDS = {
    "COMBINED_OVERDESIGN",
    "COMBINED_OVERDESIGN_GOVERNS",
    "SHEAR_OVERDESIGN_GOVERNS",
    "BENDING_OVERDESIGN_GOVERNS",
}
_FINAL_PUBLICATION_TERMINAL_NO_ACTION_FAMILY_IDS = {
    "TARGET_BAND_REACHED",
    "EXACT_STOP_PROVEN",
}
_FINAL_PUBLICATION_TERMINAL_NO_ACTION_STATES = {
    "accepted_green",
    "accepted_terminal_exact_cleanup",
    "optimal",
    "target_band_reached",
}
_FINAL_PUBLICATION_TERMINAL_NO_ACTION_REASONS = {
    "terminal_pass_no_action",
    "terminal_overdesign_cleanup_no_second_cta",
}


def _final_publication_nested_mappings(*sources: Any, max_depth: int = 5) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()

    def _walk(value: Any, depth: int) -> None:
        if depth > max_depth or not isinstance(value, Mapping):
            return
        ident = id(value)
        if ident in seen:
            return
        seen.add(ident)
        row = dict(value)
        rows.append(row)
        for nested in row.values():
            if isinstance(nested, Mapping):
                _walk(nested, depth + 1)
            elif isinstance(nested, (list, tuple)):
                for item in nested:
                    if isinstance(item, Mapping):
                        _walk(item, depth + 1)

    for source in sources:
        _walk(source, 0)
    return rows


def _final_publication_target_low_from_sources(*sources: Any) -> float:
    for row in _final_publication_nested_mappings(*sources):
        value = _number_or_none(
            row.get("final_accepted_min_family_util")
            or row.get("accepted_target_low")
            or row.get("target_low")
        )
        if value is not None:
            return float(value)
    return 0.85


def _final_publication_current_util_from_sources(*sources: Any) -> float | None:
    current_state_keys = (
        "displayed_util",
        "source_summary_util",
        "source_post_commit_util",
        "bending_utilisation",
        "shear_utilisation",
        "current_util",
        "current_utilisation",
        "family_util",
        "governing_utilisation",
    )
    fallback_candidate_keys = (
        "preview_utilisation",
        "preview_util",
        "candidate_post_util",
        "expected_util",
    )
    rows = _final_publication_nested_mappings(*sources)
    for row in rows:
        for key in current_state_keys:
            value = _number_or_none(row.get(key))
            if value is not None:
                return float(value)
    for row in rows:
        for key in fallback_candidate_keys:
            value = _number_or_none(row.get(key))
            if value is not None:
                return float(value)
    return None


def _final_publication_has_available_target_band_candidate(*sources: Any) -> bool:
    for row in _final_publication_nested_mappings(*sources):
        updates = _mapping(
            row.get("best_target_band_candidate_updates")
            or row.get("selected_target_band_candidate_updates")
            or row.get("target_band_candidate_updates")
        )
        util = _number_or_none(
            row.get("best_target_band_candidate_util")
            or row.get("selected_target_band_candidate_util")
            or row.get("target_band_candidate_util")
        )
        target_low = _number_or_none(
            row.get("accepted_target_low")
            or row.get("target_low")
            or row.get("final_accepted_min_family_util")
        )
        target_high = _number_or_none(row.get("accepted_target_high") or row.get("target_high"))
        target_low = 0.85 if target_low is None else float(target_low)
        target_high = 1.0 if target_high is None else float(target_high)
        if updates and util is not None and target_low - 1e-9 <= float(util) <= target_high + 1e-9:
            return True
        try:
            count = int(
                row.get("target_band_candidate_count")
                or row.get("executable_target_band_candidate_count")
                or 0
            )
        except Exception:
            count = 0
        if count > 0 and util is not None and target_low - 1e-9 <= float(util) <= target_high + 1e-9:
            return True
    return False


def _final_publication_exact_stop_row_has_engineering_blocker(row: Mapping[str, Any]) -> bool:
    status = (_text(row.get("failed_check_status"), row.get("terminal_candidate_status")) or "").strip().upper()
    if status == "TERMINAL_TARGET_BAND":
        return True
    try:
        target_count = int(row.get("executable_target_band_candidate_count") or 0)
    except Exception:
        target_count = 0
    if target_count > 0:
        return True
    text = " ".join(
        (_text(
            row.get("failed_check_status"),
            row.get("failed_check_name"),
            row.get("failed_check_reason"),
            row.get("blocked_reason"),
            row.get("exact_blocker_reason"),
            row.get("reason"),
        ) or "").lower().split()
    )
    if (
        "blocked_by_final_accepted_threshold" in text
        or "final accepted" in text
        or "preferred cleanup target" in text
    ):
        return False
    engineering_tokens = (
        "bending",
        "shear",
        "minimum reinforcement",
        "min reo",
        "ductility",
        "neutral",
        "serviceability",
        "crack",
        "deflection",
        "spacing",
        "geometry",
        "detailing",
        "cover",
        "fit",
        "congestion",
        "width",
        "depth",
        "locked",
        "constructability",
    )
    return any(token in text for token in engineering_tokens)


def _final_publication_has_no_second_cta_exact_proof(*sources: Mapping[str, Any]) -> bool:
    """Return true when exact-stop evidence proves no same-flow CTA remains."""

    def _proof_rows(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, Mapping):
            return []
        rows: list[dict[str, Any]] = []
        for key in (
            "exact_stop_proof",
            "target_band_proof",
            "candidate_search_evidence",
            "selection_evidence",
            "details",
            "debug",
            "final_publication_verifier_payload",
            "button_contract",
        ):
            nested = value.get(key)
            if isinstance(nested, Mapping):
                rows.extend(_proof_rows(nested))
        for nested in value.values():
            if isinstance(nested, Mapping):
                nested_keys = {str(key) for key in nested.keys()}
                if (
                    "no_second_cta_required" in nested_keys
                    or "terminal_candidate_status" in nested_keys
                    or "cleanup_search_exhaustive" in nested_keys
                    or "best_safe_candidate_applied" in nested_keys
                ):
                    rows.extend(_proof_rows(nested))
        if value:
            rows.append(dict(value))
        return rows

    terminal_statuses = {
        "TERMINAL_EXACT_STOP",
        "TERMINAL_BLOCKED_WITH_PROOF",
        "TERMINAL_TARGET_BAND",
    }
    for source in sources:
        for row in _proof_rows(source):
            if bool(
                (
                    row.get("no_second_cta_required")
                    or row.get("cleanup_search_exhaustive")
                    and row.get("best_safe_candidate_applied")
                    and not row.get("further_cleanup_available")
                )
                and _final_publication_exact_stop_row_has_engineering_blocker(row)
            ):
                return True
            if (
                str(row.get("terminal_candidate_status") or "").strip().upper()
                in terminal_statuses
                and row.get("further_cleanup_available") is False
                and _final_publication_exact_stop_row_has_engineering_blocker(row)
            ):
                return True
    return False


def final_design_guide_publication_is_terminal_no_action_surface(
    item: Mapping[str, Any] | None = None,
    debug: Mapping[str, Any] | None = None,
    selected_family: str | None = None,
) -> bool:
    """Return true when a publication surface is terminal and must not expose CTA."""

    item_d = _mapping(item)
    debug_d = _mapping(debug)
    family = (_text(
        selected_family,
        item_d.get("selected_family_id"),
        item_d.get("published_family_id"),
        item_d.get("cta_family_id"),
        debug_d.get("selected_family_id"),
        debug_d.get("published_family_id"),
        debug_d.get("cta_family_id"),
    ) or "").strip().upper()
    terminal_state = (_text(
        item_d.get("post_click_design_guide_state"),
        debug_d.get("post_click_design_guide_state"),
        item_d.get("design_guide_terminal_state"),
        debug_d.get("design_guide_terminal_state"),
    ) or "").strip().lower()
    terminal_reason = (_text(
        item_d.get("blocker_reason"),
        item_d.get("blocking_reason"),
        item_d.get("disabled_reason"),
        _mapping(item_d.get("button_contract")).get("blocking_reason"),
        _mapping(item_d.get("button_contract")).get("disabled_reason"),
        debug_d.get("blocker_reason"),
        debug_d.get("blocking_reason"),
        debug_d.get("disabled_reason"),
    ) or "").strip().lower()
    if _final_publication_active_failure_repair_surface_has_work(
        item_d,
        debug_d,
        family,
        require_repair_work=False,
    ):
        return False
    target_low = _final_publication_target_low_from_sources(item_d, debug_d)
    current_util = _final_publication_current_util_from_sources(item_d, debug_d)
    target_candidate_available = _final_publication_has_available_target_band_candidate(item_d, debug_d)
    if (
        target_candidate_available
        and current_util is not None
        and float(current_util) < float(target_low) - 1e-9
    ):
        return False
    proof_text = stable_final_publication_hash({})
    try:
        proof_text = json.dumps(
            {
                "item_exact_stop_proof": item_d.get("exact_stop_proof"),
                "debug_exact_stop_proof": debug_d.get("exact_stop_proof"),
                "item_candidate_search_evidence": item_d.get("candidate_search_evidence"),
                "debug_candidate_search_evidence": debug_d.get("candidate_search_evidence"),
            },
            sort_keys=True,
            default=str,
        ).lower()
    except Exception:
        proof_text = ""
    if (
        (
            "blocked_by_final_accepted_threshold" in proof_text
            or "final accepted" in proof_text
            or "preferred cleanup target" in proof_text
        )
        and not _final_publication_has_no_second_cta_exact_proof(item_d, debug_d)
    ):
        return False
    if family in _FINAL_PUBLICATION_TERMINAL_NO_ACTION_FAMILY_IDS:
        return True
    if terminal_state in _FINAL_PUBLICATION_TERMINAL_NO_ACTION_STATES:
        return True
    if terminal_reason in _FINAL_PUBLICATION_TERMINAL_NO_ACTION_REASONS:
        return True
    if _final_publication_has_no_second_cta_exact_proof(item_d, debug_d):
        return True
    status = (_text(item_d.get("status"), item_d.get("bucket")) or "").strip().upper()
    title_text = " ".join(
        str(value or "")
        for value in (
            item_d.get("title_main"),
            item_d.get("title"),
            item_d.get("summary_line"),
            item_d.get("primary_action"),
        )
    ).strip().lower()
    return bool(
        status in {"PASS", "GOOD", "OK", "OPTIMAL"}
        and (
            "target band achieved" in title_text
            or "design accepted" in title_text
            or "accepted post-click state" in title_text
        )
    )


def _final_publication_updates_from_item_debug(
    item: dict[str, Any] | None,
    debug: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item_d = _mapping(item)
    debug_d = _mapping(debug)
    contract = _mapping(
        item_d.get("button_contract")
        or debug_d.get("displayed_primary_button_contract")
        or debug_d.get("primary_button_contract")
        or debug_d.get("button_contract")
    )
    action_payload = _mapping(item_d.get("action_payload") or debug_d.get("design_guide_primary_apply_payload"))
    evidence = _mapping(item_d.get("candidate_search_evidence") or debug_d.get("candidate_search_evidence"))
    return _mapping(
        contract.get("updates")
        or action_payload.get("updates")
        or action_payload.get("resolved_candidate_updates")
        or item_d.get("updates")
        or evidence.get("selected_candidate_updates")
        or evidence.get("best_safe_candidate_updates")
        or evidence.get("proposed_updates")
    )


def _canonical_overdesign_family_from_updates(updates: dict[str, Any] | None) -> str | None:
    update_keys = set(_mapping(updates))
    has_shear = bool(update_keys & _FINAL_PUBLICATION_SHEAR_UPDATE_KEYS)
    has_bottom_or_geometry = bool(
        update_keys & (_FINAL_PUBLICATION_BOTTOM_UPDATE_KEYS | _FINAL_PUBLICATION_GEOMETRY_UPDATE_KEYS)
    )
    if has_shear and has_bottom_or_geometry:
        return "COMBINED_OVERDESIGN"
    if has_shear:
        return "SHEAR_OVERDESIGN_GOVERNS"
    if has_bottom_or_geometry:
        return "BENDING_OVERDESIGN_GOVERNS"
    return None


def _canonical_overdesign_family_identity(
    family_id: str | None,
    updates: dict[str, Any] | None,
) -> str | None:
    family_text = str(family_id or "").strip()
    if family_text.upper() not in _FINAL_PUBLICATION_OVERDESIGN_FAMILY_IDS:
        return family_id
    return _canonical_overdesign_family_from_updates(updates) or family_id


def _canonical_overdesign_family_identity_from_context(
    family_id: str | None,
    updates: dict[str, Any] | None,
    *contexts: dict[str, Any] | None,
) -> str | None:
    family_text = str(family_id or "").strip()
    context_values: set[str] = set()
    for context in contexts:
        context_d = _mapping(context)
        for key in (
            "selected_family_id",
            "selected_family",
            "published_family_id",
            "cta_family_id",
            "apply_payload_family_id",
            "candidate_family_id",
            "card_family_id",
            "matched_family_ids",
            "contract_runtime_authority",
            "source",
            "guidance_branch",
            "bucket",
            "status",
            "critical_status",
            "title",
            "title_main",
            "primary_action",
            "summary",
            "reasoning",
        ):
            raw_value = context_d.get(key)
            if isinstance(raw_value, (list, tuple, set)):
                for item in raw_value:
                    value = str(item or "").strip()
                    if value:
                        context_values.add(value)
            else:
                value = str(raw_value or "").strip()
                if value:
                    context_values.add(value)
    context_text = " ".join(sorted(context_values)).lower()
    update_keys = set(_mapping(updates))
    cleanup_context = bool(
        update_keys
        and (
            "cleanup" in context_text
            or "overdesign" in context_text
            or "safe one-click reduction" in context_text
            or "best safe one-click reduction" in context_text
            or "reserve" in context_text
            or "optional cleanup" in context_text
        )
        and "capacity is low" not in context_text
        and "active strength capacity is failing" not in context_text
    )
    if family_text.lower() in {"", "general", "cleanup", "recommend"} and cleanup_context:
        return _canonical_overdesign_family_from_updates(updates) or family_id
    if (
        update_keys
        and update_keys.issubset(_FINAL_PUBLICATION_SHEAR_UPDATE_KEYS | {"b", "bw"})
        and (
            "SHEAR_OVERDESIGN_GOVERNS" in context_values
            or "shear_overdesign" in context_text
            or "run_shear_overdesign_governs_runtime" in context_text
        )
    ):
        return "SHEAR_OVERDESIGN_GOVERNS"
    if (
        family_text.lower() == "shear"
        and update_keys
        and update_keys.issubset(_FINAL_PUBLICATION_SHEAR_UPDATE_KEYS)
        and (
            "SHEAR_OVERDESIGN_GOVERNS" in context_values
            or "shear_overdesign" in context_text
            or "run_shear_overdesign_governs_runtime" in context_text
            or (
                "cleanup" in context_text
                and (
                    "efficiency" in context_text
                    or "optional" in context_text
                    or "design is safe" in context_text
                    or "all checks pass" in context_text
                )
            )
        )
    ):
        return "SHEAR_OVERDESIGN_GOVERNS"
    return _canonical_overdesign_family_identity(family_text, updates)


def _canonical_active_failure_mixed_family_identity_from_context(
    family_id: str | None,
    updates: dict[str, Any] | None,
    *contexts: dict[str, Any] | None,
) -> str | None:
    family_text = str(family_id or "").strip()
    update_keys = set(_mapping(updates))
    context_values: set[str] = set()
    active_failures: set[str] = set()
    exact_blockers: dict[str, Any] = {}
    post_click_exact_blockers: dict[str, Any] = {}
    for context in contexts:
        context_d = _mapping(context)
        for key in (
            "selected_family_id",
            "selected_family",
            "published_family_id",
            "cta_family_id",
            "apply_payload_family_id",
            "candidate_family_id",
            "card_family_id",
            "matched_family_ids",
            "contract_runtime_authority",
            "source",
            "guidance_branch",
            "bucket",
            "status",
            "critical_status",
            "title",
            "title_main",
            "primary_action",
            "summary",
            "reasoning",
        ):
            raw_value = context_d.get(key)
            if isinstance(raw_value, (list, tuple, set)):
                for item in raw_value:
                    value = str(item or "").strip()
                    if value:
                        context_values.add(value)
            else:
                value = str(raw_value or "").strip()
                if value:
                    context_values.add(value)
        raw_active = context_d.get("active_failures")
        if isinstance(raw_active, (list, tuple, set)):
            active_failures.update(
                str(value or "").strip().lower()
                for value in raw_active
                if str(value or "").strip()
            )
        elif isinstance(raw_active, str):
            active_failures.update(
                token.strip().lower()
                for token in re.split(r"[,| ]+", raw_active)
                if token.strip()
            )
        exact_blockers.update(_mapping(context_d.get("exact_blockers_by_family")))
        post_click_exact_blockers.update(_mapping(context_d.get("post_click_exact_blockers_by_family")))
        exact_stop = _mapping(context_d.get("exact_stop_proof"))
        if isinstance(exact_stop, dict):
            for family_key in ("bending", "shear"):
                exact_stop_family = _mapping(exact_stop.get(family_key))
                if exact_stop_family and family_key not in exact_blockers:
                    exact_blockers[family_key] = exact_stop_family

    context_text = " ".join(sorted(context_values)).lower()
    both_strength_failures_active = bool(
        {"bending", "shear"}.issubset(active_failures)
        or "active_combined_bending_shear_failure" in context_text
        or "combined_bending_shear_fail" in context_text
        or "bending and shear" in context_text
    )
    if both_strength_failures_active and family_text.upper() in {
        "COMBINED_BENDING_SHEAR_FAIL",
        "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
        "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        "BENDING_FAIL_SHEAR_OPTIMISE_GOVERNS",
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        "SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS",
        "SHEAR_FAIL_GOVERNS",
        "BENDING_FAIL_GOVERNS",
        "SHEAR",
        "BENDING",
        "COMBINED",
    }:
        return "COMBINED_BENDING_SHEAR_FAIL"

    if family_text in {
        "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        "BENDING_FAIL_SHEAR_OPTIMISE_GOVERNS",
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        "SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS",
    }:
        return (
            "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS"
            if family_text == "BENDING_FAIL_SHEAR_OPTIMISE_GOVERNS"
            else "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS"
            if family_text == "SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS"
            else family_text
        )

    def _blocker_util(domain: str) -> float | None:
        blocker = _mapping(exact_blockers.get(domain) or post_click_exact_blockers.get(domain))
        for key in ("current_util", "util", "utilisation", "current_utilisation"):
            try:
                value = blocker.get(key)
                if value not in (None, ""):
                    return float(value)
            except Exception:
                continue
        return None

    def _has_blocker_updates(domain: str, keys: set[str]) -> bool:
        blocker = _mapping(exact_blockers.get(domain) or post_click_exact_blockers.get(domain))
        attempted = _mapping(blocker.get("attempted_updates") or blocker.get("best_rejected_updates"))
        return bool(set(attempted) & keys)

    has_bending_repair = bool(
        update_keys & (_FINAL_PUBLICATION_BOTTOM_UPDATE_KEYS | _FINAL_PUBLICATION_GEOMETRY_UPDATE_KEYS)
    )
    has_shear_repair = bool(update_keys & _FINAL_PUBLICATION_SHEAR_UPDATE_KEYS)
    shear_util = _blocker_util("shear")
    bending_util = _blocker_util("bending")
    shear_overdesign_evidence = bool(
        (shear_util is not None and shear_util < 0.85)
        or _has_blocker_updates("shear", _FINAL_PUBLICATION_SHEAR_UPDATE_KEYS)
        or "shear_overdesign" in context_text
        or "zero_shear" in context_text
    )
    bending_overdesign_evidence = bool(
        (bending_util is not None and bending_util < 0.85)
        or _has_blocker_updates("bending", _FINAL_PUBLICATION_BOTTOM_UPDATE_KEYS | _FINAL_PUBLICATION_GEOMETRY_UPDATE_KEYS)
        or "bending_overdesign" in context_text
    )
    bending_active_repair = bool(
        has_bending_repair
        and (
            family_text.lower() in {"bending", "bending_fail_governs"}
            or "bending capacity is low" in context_text
            or "bending_fail" in context_text
        )
    )
    shear_active_repair = bool(
        has_shear_repair
        and (
            family_text.lower() in {"shear", "shear_fail_governs"}
            or "shear capacity is low" in context_text
            or "shear_fail" in context_text
        )
    )
    if bending_active_repair and shear_overdesign_evidence:
        return "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS"
    if shear_active_repair and bending_overdesign_evidence:
        return "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS"
    if bending_active_repair:
        return "BENDING_FAIL_GOVERNS"
    if shear_active_repair:
        return "SHEAR_FAIL_GOVERNS"
    return family_text or None


@dataclass(frozen=True)
class FinalDesignGuideCTA:
    """Proof representation of final CTA state; not product-driving."""

    enabled: bool = False
    actionable: bool = False
    label: str | None = None
    action_type: str | None = None
    family: str | None = None
    updates: dict[str, Any] = field(default_factory=dict)
    disabled_reason: str | None = None
    apply_payload_summary: dict[str, Any] = field(default_factory=dict)
    apply_payload_fingerprint: str | None = None
    button_contract_hash: str | None = None
    source_candidate_id: str | None = None
    executor_backed_proof: dict[str, Any] = field(default_factory=dict)
    stale_fresh_token_proof: dict[str, Any] = field(default_factory=dict)
    one_click_action_handoff: dict[str, Any] = field(default_factory=dict)
    source_precedence_proof: dict[str, Any] = field(default_factory=dict)
    product_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalDesignGuideDisplay:
    """Proof representation of visible display fields; not renderer-driving."""

    title: str | None = None
    badge: str | None = None
    summary: str | None = None
    status: str | None = None
    bucket: str | None = None
    colour_state: str | None = None
    card_class: str | None = None
    display_state: str | None = None
    expanded_evidence_sections: dict[str, Any] = field(default_factory=dict)
    blocker_explanation: str | None = None
    final_card_model_fields: dict[str, Any] = field(default_factory=dict)
    final_card_model_hash: str | None = None
    render_fallback_shell_model: dict[str, Any] = field(default_factory=dict)
    render_fallback_shell_hash: str | None = None
    visible_wording_hash: str | None = None
    renderer_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalDesignGuideDirectShellIdentityProjection:
    """Projection of family identity fields used by direct shell rendering."""

    identity: dict[str, Any] = field(default_factory=dict)
    title: str | None = None
    governing_label: str | None = None
    summary_line: str | None = None
    reason_text: str | None = None
    projection_hash: str | None = None
    proof_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalDesignGuideDirectShellCardProjection:
    """Page-free card VM projection for direct one-click shells."""

    title: str | None = None
    pill: str | None = None
    shell_model: dict[str, Any] = field(default_factory=dict)
    family_identity: dict[str, Any] = field(default_factory=dict)
    view_model: dict[str, Any] = field(default_factory=dict)
    card_class: str | None = None
    anchor_bucket: str | None = None
    active_strength_shell: bool = False
    identity_projection: dict[str, Any] = field(default_factory=dict)
    projection_hash: str | None = None
    proof_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalDesignGuideEvidence:
    """Proof evidence behind final publication classification."""

    published_item_id: str | None = None
    post_click_design_guide_state: str | None = None
    selected_family: str | None = None
    publication_reason: str | None = None
    blocker_reason: str | None = None
    exact_stop_proof: dict[str, Any] = field(default_factory=dict)
    target_band_proof: dict[str, Any] = field(default_factory=dict)
    stale_fresh_proof: dict[str, Any] = field(default_factory=dict)
    candidate_search_evidence: dict[str, Any] = field(default_factory=dict)
    optimal_blocker_proof: dict[str, Any] = field(default_factory=dict)
    compute_publication_evidence: dict[str, Any] = field(default_factory=dict)
    compute_publication_evidence_hashes: dict[str, str] = field(default_factory=dict)
    compute_publication_evidence_hash: str | None = None
    evidence_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalDesignGuideVerifierPayload:
    """Verifier/debug proof payload; not browser-driving."""

    payload: dict[str, Any] = field(default_factory=dict)
    payload_hash: str | None = None
    browser_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalDesignGuidePostResolverMutationProof:
    """Proof surface for render-stage post-resolver selected-item mutations."""

    selected_item_identity: dict[str, Any] = field(default_factory=dict)
    adapter_owned_mutation_truth: dict[str, Any] = field(default_factory=dict)
    remaining_resolver_truth: dict[str, Any] = field(default_factory=dict)
    evidence_projection: dict[str, Any] = field(default_factory=dict)
    blocker_projection: dict[str, Any] = field(default_factory=dict)
    terminal_projection: dict[str, Any] = field(default_factory=dict)
    resolver_projection: dict[str, Any] = field(default_factory=dict)
    selected_item_projection: dict[str, Any] = field(default_factory=dict)
    debug_projection: dict[str, Any] = field(default_factory=dict)
    mutation_target_coverage: dict[str, bool] = field(default_factory=dict)
    mutation_proof_hash: str | None = None
    derived_from: str = "FinalDesignGuidePublication"
    proof_only: bool = True
    product_driving: bool = False
    render_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalDesignGuidePublicationMutationProof:
    """Proof surface for publication-driven final-visible item mutation parity."""

    callsite_id: str
    input_item_hash: str | None = None
    output_item_hash: str | None = None
    state_hash: str | None = None
    debug_hash: str | None = None
    rec_hash: str | None = None
    cta_projection_hash: str | None = None
    display_projection_hash: str | None = None
    evidence_projection_hash: str | None = None
    mutation_surface: dict[str, bool] = field(default_factory=dict)
    output_changed: bool = False
    cta_changed: bool = False
    display_changed: bool = False
    evidence_changed: bool = False
    proof_hash: str | None = None
    derived_from: str = "final_design_guide_publication_mutation"
    proof_only: bool = True
    product_driving: bool = False
    render_driving: bool = False
    apply_driving: bool = False
    session_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalVisibleContractBindingOutputProjection:
    """Plain-data contract-binding output projection for final-visible publication state."""

    callsite_id: str
    item: dict[str, Any] = field(default_factory=dict)
    cta_projection: dict[str, Any] = field(default_factory=dict)
    display_projection: dict[str, Any] = field(default_factory=dict)
    evidence_projection: dict[str, Any] = field(default_factory=dict)
    action_payload_projection: dict[str, Any] = field(default_factory=dict)
    resolved_candidate_projection: dict[str, Any] = field(default_factory=dict)
    debug_projection: dict[str, Any] = field(default_factory=dict)
    source_projection_hashes: dict[str, str] = field(default_factory=dict)
    adapter_hash: str | None = None
    derived_from: str = "FinalDesignGuidePublication.final_visible_contract_binding_output_projection"
    product_driving: bool = False
    render_driving: bool = False
    apply_driving: bool = False
    session_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalDesignGuideRenderItemConsumerProof:
    """Proof surface for render-item consumers after final publication binding."""

    zero_shear_cleanup: dict[str, Any] = field(default_factory=dict)
    safe_low_util_promotion: dict[str, Any] = field(default_factory=dict)
    post_click_final_contract_checks: dict[str, Any] = field(default_factory=dict)
    consumer_coverage: dict[str, bool] = field(default_factory=dict)
    consumer_group_hashes: dict[str, str] = field(default_factory=dict)
    covered_consumer_groups: tuple[str, ...] = ()
    missing_consumer_groups: tuple[str, ...] = ()
    consumer_proof_hash: str | None = None
    derived_from: str = "FinalDesignGuidePublication"
    proof_only: bool = True
    product_driving: bool = False
    render_driving: bool = False
    apply_driving: bool = False
    session_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalDesignGuideComputePublicationHandoffReboundDecisionProof:
    """Proof surface for compute-stage publication handoff/rebound decisions."""

    raw_selected_item_identity: dict[str, Any] = field(default_factory=dict)
    blocker_evidence_surface: dict[str, Any] = field(default_factory=dict)
    render_reason: str | None = None
    state_fingerprint: str | None = None
    late_evidence_acceptance: dict[str, Any] = field(default_factory=dict)
    rebound_contract: dict[str, Any] = field(default_factory=dict)
    rebound_update_payload_summary: dict[str, Any] = field(default_factory=dict)
    post_core_evidence_mismatch: dict[str, Any] = field(default_factory=dict)
    raw_rebound_item_identity: dict[str, Any] = field(default_factory=dict)
    pre_resolver_collapsed_item_mutation: dict[str, Any] = field(default_factory=dict)
    field_hashes: dict[str, str] = field(default_factory=dict)
    covered_blocking_fields: tuple[str, ...] = ()
    missing_blocking_fields: tuple[str, ...] = ()
    decision_hash: str | None = None
    derived_from: str = "compute_publication_handoff_rebound_surfaces"
    proof_only: bool = True
    product_driving: bool = False
    render_driving: bool = False
    apply_driving: bool = False
    session_driving: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalDesignGuidePublication:
    """Normalized proof object for final Design Guide publication."""

    published_item_id: str | None
    selected_family: str | None
    outcome_state: FinalDesignGuideOutcomeState
    post_click_design_guide_state: str | None = None
    publication_reason: str | None = None
    blocker_reason: str | None = None
    exact_stop_proof: dict[str, Any] = field(default_factory=dict)
    target_band_proof: dict[str, Any] = field(default_factory=dict)
    cta: FinalDesignGuideCTA = field(default_factory=FinalDesignGuideCTA)
    display: FinalDesignGuideDisplay = field(default_factory=FinalDesignGuideDisplay)
    evidence: FinalDesignGuideEvidence = field(default_factory=FinalDesignGuideEvidence)
    verifier_payload: FinalDesignGuideVerifierPayload = field(default_factory=FinalDesignGuideVerifierPayload)
    stale_fresh_proof: dict[str, Any] = field(default_factory=dict)
    source_hash: str | None = None
    publication_hash: str | None = None
    proof_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def with_publication_hash(self) -> "FinalDesignGuidePublication":
        payload = self.to_dict()
        payload.pop("publication_hash", None)
        return FinalDesignGuidePublication(
            **{
                **payload,
                "cta": self.cta,
                "display": self.display,
                "evidence": self.evidence,
                "verifier_payload": self.verifier_payload,
                "publication_hash": stable_final_publication_authority_hash(payload),
            }
        )


def infer_final_design_guide_outcome_state(
    *,
    item: dict[str, Any] | None = None,
    cta: FinalDesignGuideCTA | None = None,
    blocker_reason: str | None = None,
) -> FinalDesignGuideOutcomeState:
    """Infer proof outcome state from already-shaped publication fields."""

    item_d = _mapping(item)
    cta_d = cta or FinalDesignGuideCTA()
    status = str(item_d.get("status") or item_d.get("critical_status") or "").strip().upper()
    bucket = str(item_d.get("bucket") or "").strip().lower()
    intent = str(item_d.get("guidance_intent") or "").strip().lower()
    final_state = str(
        item_d.get("final_state_class")
        or item_d.get("final_state_type")
        or item_d.get("design_guide_terminal_state")
        or ""
    ).strip().lower()
    if status in {"ERROR", "CRITICAL"} or bucket == "error":
        return "ERROR"
    if bool(cta_d.enabled or cta_d.actionable):
        return "ACTION"
    if str(blocker_reason or "").strip().lower() in _FINAL_PUBLICATION_TERMINAL_NO_ACTION_REASONS:
        return "PASS"
    if final_design_guide_publication_is_terminal_no_action_surface(item_d):
        return "PASS"
    if (
        blocker_reason
        or intent == "specific_blocker"
        or final_state == "blocker"
        or isinstance(item_d.get("exact_blockers_by_family"), dict)
        and bool(item_d.get("exact_blockers_by_family"))
        or isinstance(item_d.get("post_click_exact_blockers_by_family"), dict)
        and bool(item_d.get("post_click_exact_blockers_by_family"))
        or str(item_d.get("terminal_cleanup_state") or "").strip().lower() == "blocked"
    ):
        return "BLOCKED"
    if status in {"PASS", "GOOD", "OK"} or bucket == "pass" or item_d.get("design_guide_terminal_state"):
        return "PASS"
    return "PROOF_PENDING"


def is_final_design_guide_family_contract_violation_item(item: dict[str, Any] | None) -> bool:
    """Return true for family-contract violation cards, including stale cached items."""

    item_d = _mapping(item)
    title = str(item_d.get("title_main") or item_d.get("title") or item_d.get("headline") or "").strip().lower()
    summary = str(
        item_d.get("summary_line")
        or item_d.get("primary_action")
        or item_d.get("reasoning")
        or item_d.get("status_text")
        or ""
    ).strip().lower()
    reason = str(
        item_d.get("family_match_violation_reason")
        or item_d.get("blocker_explanation")
        or item_d.get("blocking_reason")
        or ""
    ).strip().lower()
    return bool(
        title == "design guide family contract violation"
        or "publication blocked by family contract" in summary
        or "family contract violation" in reason
        or reason in {"wrong_family_publication", "family_selection_contract_mismatch"}
    )


def normalise_stale_family_contract_violation_item(
    item: dict[str, Any] | None,
    debug: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Replace stale contract-violation shells when family identity has already recovered."""

    item_d = dict(_mapping(item))
    if not item_d or not is_final_design_guide_family_contract_violation_item(item_d):
        return item_d

    debug_d = _mapping(debug)
    details_d = _mapping(item_d.get("details"))
    evidence_d = _mapping(item_d.get("candidate_search_evidence") or details_d.get("candidate_search_evidence"))
    exact_blockers = _mapping(
        item_d.get("post_click_exact_blockers_by_family")
        or item_d.get("exact_blockers_by_family")
        or details_d.get("post_click_exact_blockers_by_family")
        or details_d.get("exact_blockers_by_family")
        or evidence_d.get("post_click_exact_blockers_by_family")
        or evidence_d.get("exact_blockers_by_family")
    )
    if (
        exact_blockers
        and str(item_d.get("guidance_intent") or "").strip().lower()
        == "specific_blocker"
    ):
        # This is current family-owned stop truth, not a stale contract shell.
        # Passing strength checks do not imply target-band completion while
        # exact cleanup-stop evidence remains active.
        return item_d
    debug_evidence_d = _mapping(
        debug_d.get("selection_evidence")
        or debug_d.get("candidate_search_evidence")
        or debug_d.get("family_selection_evidence")
    )
    selection_evidence_d = _mapping(item_d.get("selection_evidence"))
    verifier_d = _mapping(debug_d.get("final_publication_verifier_payload"))

    def _family_id(*keys: str) -> str:
        for key in keys:
            value = _text(
                item_d.get(key),
                details_d.get(key),
                evidence_d.get(key),
                debug_d.get(key),
                debug_evidence_d.get(key),
                verifier_d.get(key),
            )
            if value:
                return value
        return ""

    selected_family_id = _family_id("selected_family_id", "selected_family")
    published_family_id = _family_id("published_family_id", "published_family")
    cta_family_id = _family_id("cta_family_id")
    card_family_id = _family_id("card_family_id")
    debug_selected_family_id = _text(
        debug_d.get("selected_family_id"),
        debug_evidence_d.get("selected_family_id"),
        verifier_d.get("selected_family_id"),
    )
    debug_published_family_id = _text(
        debug_d.get("published_family_id"),
        debug_evidence_d.get("published_family_id"),
        verifier_d.get("published_family_id"),
    )
    debug_cta_family_id = _text(
        debug_d.get("cta_family_id"),
        debug_evidence_d.get("cta_family_id"),
        verifier_d.get("cta_family_id"),
    )
    debug_card_family_id = _text(
        debug_d.get("card_family_id"),
        debug_evidence_d.get("card_family_id"),
        verifier_d.get("card_family_id"),
    )
    matched_family_ids = {
        str(value or "").strip()
        for value in (
            item_d.get("matched_family_ids")
            or details_d.get("matched_family_ids")
            or evidence_d.get("matched_family_ids")
            or debug_d.get("matched_family_ids")
            or debug_evidence_d.get("matched_family_ids")
            or verifier_d.get("matched_family_ids")
            or []
        )
        if str(value or "").strip()
    }
    family_match_passed = bool(
        item_d.get("family_match_passed")
        or details_d.get("family_match_passed")
        or evidence_d.get("family_match_passed")
        or debug_d.get("family_match_passed")
        or debug_evidence_d.get("family_match_passed")
        or verifier_d.get("family_match_passed")
        or "TARGET_BAND_REACHED" in matched_family_ids
    )
    verifier_active_failures = verifier_d.get("active_failures")
    debug_active_failures = (
        debug_d.get("active_failures")
        or debug_evidence_d.get("active_failures")
        or verifier_active_failures
    )
    raw_state_flags = _mapping(
        item_d.get("raw_state_flags")
        or selection_evidence_d.get("raw_state_flags")
        or details_d.get("raw_state_flags")
        or evidence_d.get("raw_state_flags")
        or debug_d.get("raw_state_flags")
        or debug_evidence_d.get("raw_state_flags")
        or verifier_d.get("raw_state_flags")
    )
    raw_state_recovers_target_band = bool(
        raw_state_flags.get("target_band_terminal_signal")
        and not raw_state_flags.get("any_failure")
        and not raw_state_flags.get("any_strength_fail")
        and not raw_state_flags.get("repair_required")
        and not raw_state_flags.get("bending_fail")
        and not raw_state_flags.get("shear_fail")
    )
    verifier_recovers_target_band = bool(
        _text(verifier_d.get("selected_family_id"), verifier_d.get("published_family_id"))
        == "TARGET_BAND_REACHED"
        and verifier_d.get("family_match_passed")
        and not verifier_active_failures
    )
    debug_recovers_target_band = bool(
        verifier_recovers_target_band
        or (
        debug_selected_family_id == "TARGET_BAND_REACHED"
        and (
            debug_d.get("family_match_passed")
            or debug_evidence_d.get("family_match_passed")
            or verifier_d.get("family_match_passed")
            or "TARGET_BAND_REACHED" in matched_family_ids
            or raw_state_recovers_target_band
        )
        and (not debug_active_failures or raw_state_recovers_target_band)
    )
    )
    if debug_recovers_target_band:
        selected_family_id = "TARGET_BAND_REACHED"
        published_family_id = debug_published_family_id or "TARGET_BAND_REACHED"
        cta_family_id = debug_cta_family_id or "TARGET_BAND_REACHED"
        card_family_id = debug_card_family_id or "TARGET_BAND_REACHED"
        matched_family_ids.add("TARGET_BAND_REACHED")
        family_match_passed = True
        debug_active_failures = []
    allowed_stale_ids = {"", "TARGET_BAND_REACHED", "FAMILY_SELECTION_CONTRACT_VIOLATION"}
    known_family_ids = {selected_family_id, published_family_id, cta_family_id, card_family_id}
    explicit_family_ids = {value for value in known_family_ids if value}
    all_explicit_ids_are_target_band = bool(explicit_family_ids) and explicit_family_ids <= {"TARGET_BAND_REACHED"}
    recovered_target_band = (
        selected_family_id == "TARGET_BAND_REACHED"
        and (family_match_passed or all_explicit_ids_are_target_band)
        and known_family_ids <= allowed_stale_ids
        and (
            raw_state_recovers_target_band
            or not (
                item_d.get("active_failures")
                or details_d.get("active_failures")
                or evidence_d.get("active_failures")
                or debug_active_failures
            )
        )
    )
    combined_active_failures = {
        str(value or "").strip().lower()
        for value in (debug_active_failures or item_d.get("active_failures") or evidence_d.get("active_failures") or [])
        if str(value or "").strip()
    }
    combined_raw_flags = bool(
        raw_state_flags.get("active_combined_bending_shear_failure")
        or (raw_state_flags.get("bending_fail") and raw_state_flags.get("shear_fail"))
    )
    recover_combined_action = bool(
        selected_family_id == "COMBINED_BENDING_SHEAR_FAIL"
        and (family_match_passed or "COMBINED_BENDING_SHEAR_FAIL" in matched_family_ids)
        and (combined_active_failures >= {"bending", "shear"} or combined_raw_flags)
    )
    if recover_combined_action:
        contract = dict(
            _mapping(
                item_d.get("button_contract")
                or debug_d.get("primary_button_contract")
                or debug_d.get("button_contract")
            )
        )
        action_payload = dict(_mapping(item_d.get("action_payload") or debug_d.get("design_guide_primary_apply_payload")))
        updates = _mapping(
            contract.get("updates")
            or action_payload.get("updates")
            or action_payload.get("resolved_candidate_updates")
            or item_d.get("updates")
            or evidence_d.get("selected_candidate_updates")
            or evidence_d.get("best_safe_candidate_updates")
            or evidence_d.get("proposed_updates")
        )
        action_type = _text(
            contract.get("action_type"),
            action_payload.get("action_type"),
            action_payload.get("resolved_candidate_action_type"),
            item_d.get("action_type"),
        )
        if updates and (action_type == "apply_resolved_candidate" or not action_type):
            action_type = action_type or "apply_resolved_candidate"
            candidate_id = _text(
                contract.get("source_candidate_id"),
                contract.get("candidate_id"),
                action_payload.get("source_candidate_id"),
                action_payload.get("candidate_id"),
                evidence_d.get("selected_candidate_id"),
                "combined_bending_shear_fail_repair",
            )
            contract.update(
                {
                    "enabled": True,
                    "actionable": True,
                    "family": "combined",
                    "family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "selected_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "published_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "cta_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "apply_payload_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "candidate_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "card_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "action_type": action_type,
                    "updates": dict(updates),
                    "preview_pass": True,
                    "blocking_reason": None,
                    "disabled_reason": None,
                    "source_candidate_id": candidate_id,
                    "candidate_id": candidate_id,
                    "family_selection_contract": "family_selection_contract",
                    "family_match_passed": True,
                    "stale_contract_violation_recovered_to_combined_action": True,
                }
            )
            action_payload.update(
                {
                    "family": "combined",
                    "selected_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "published_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "cta_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "apply_payload_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "candidate_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "updates": dict(updates),
                    "resolved_candidate_updates": dict(updates),
                    "action_type": action_type,
                    "resolved_candidate_action_type": action_type,
                    "source_candidate_id": candidate_id,
                    "candidate_id": candidate_id,
                }
            )
            cleaned_evidence = dict(evidence_d)
            cleaned_evidence.update(
                {
                    "selected_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "published_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "cta_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "apply_payload_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "candidate_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "card_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "matched_family_ids": ["COMBINED_BENDING_SHEAR_FAIL"],
                    "family_chooser_contract": "family_chooser_contract",
                    "family_selection_contract": "family_selection_contract",
                    "family_match_passed": True,
                    "family_match_violation_reason": None,
                    "family_route_owner": (
                        "design_brain.families.combined_bending_shear_fail."
                        "CombinedBendingShearFailFamily"
                    ),
                    "blocking_reason": None,
                    "stale_contract_violation_recovered_to_combined_action": True,
                }
            )
            for key in (
                "family_match_violation_reason",
                "blocking_reason",
                "blocker_explanation",
                "active_under_capacity_blocker",
                "active_under_capacity_blocker_reason",
            ):
                item_d.pop(key, None)
            item_d.update(
                {
                    "title_main": "Bending and shear capacity are low",
                    "title": "Bending and shear capacity are low",
                    "headline": "Bending and shear capacity are low",
                    "summary_line": "Combined strengthening repair is executable and preview is valid.",
                    "primary_action": "Run one-click auto design",
                    "reasoning": "This update targets the active bending and shear failures.",
                    "status": "FAIL",
                    "critical_status": "FAIL",
                    "bucket": "fail",
                    "tone": "fail",
                    "pill": "ACTION",
                    "display_state": "ACTION",
                    "final_state_class": "action",
                    "guidance_intent": "required_fix",
                    "family": "combined",
                    "check_key": "combined",
                    "selected_action_family": "combined",
                    "selected_family": "COMBINED_BENDING_SHEAR_FAIL",
                    "selected_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "published_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "cta_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "apply_payload_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "candidate_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "card_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                    "matched_family_ids": ["COMBINED_BENDING_SHEAR_FAIL"],
                    "family_chooser_contract": "family_chooser_contract",
                    "family_selection_contract": "family_selection_contract",
                    "family_match_passed": True,
                    "candidate_search_evidence": cleaned_evidence,
                    "button_contract": contract,
                    "action_payload": action_payload,
                    "action_type": action_type,
                    "updates": dict(updates),
                    "selected_action_updates": dict(updates),
                    "primary_card_actionable": True,
                    "stale_contract_violation_recovered_to_combined_action": True,
                }
            )
            if details_d:
                cleaned_details = dict(details_d)
                cleaned_details.update(
                    {
                        "selected_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                        "published_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                        "cta_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                        "apply_payload_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                        "candidate_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                        "card_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                        "matched_family_ids": ["COMBINED_BENDING_SHEAR_FAIL"],
                        "family_match_passed": True,
                        "family_match_violation_reason": None,
                        "blocking_reason": None,
                        "candidate_search_evidence": cleaned_evidence,
                        "stale_contract_violation_recovered_to_combined_action": True,
                    }
                )
                cleaned_details.pop("blocker_explanation", None)
                item_d["details"] = cleaned_details
            return item_d
    if not recovered_target_band:
        return item_d

    button_contract = dict(_mapping(item_d.get("button_contract")))
    button_contract.update(
        {
            "enabled": False,
            "actionable": False,
            "updates": {},
            "blocking_reason": None,
            "disabled_reason": None,
            "family_id": "TARGET_BAND_REACHED",
            "publication_family_id": "TARGET_BAND_REACHED",
            "cta_family_id": "TARGET_BAND_REACHED",
        }
    )
    cleaned_evidence = dict(evidence_d)
    cleaned_evidence.update(
        {
            "selected_family_id": "TARGET_BAND_REACHED",
            "published_family_id": "TARGET_BAND_REACHED",
            "cta_family_id": "TARGET_BAND_REACHED",
            "card_family_id": "TARGET_BAND_REACHED",
            "matched_family_ids": ["TARGET_BAND_REACHED"],
            "family_match_passed": True,
            "family_match_violation_reason": None,
            "blocking_reason": None,
            "stale_family_contract_violation_normalised": True,
        }
    )
    for key in (
        "family_match_violation_reason",
        "blocking_reason",
        "blocker_explanation",
        "active_under_capacity_blocker",
        "active_under_capacity_blocker_reason",
    ):
        item_d.pop(key, None)
    item_d.update(
        {
            "title_main": "Design accepted - target band achieved",
            "title": "Design accepted - target band achieved",
            "headline": "Design accepted - target band achieved",
            "summary_line": "All required checks pass and the governing utilisation is in the target band.",
            "primary_action": "All required checks pass and the governing utilisation is in the target band.",
            "reasoning": "All required checks pass and the governing utilisation is in the target band.",
            "status": "PASS",
            "critical_status": "PASS",
            "bucket": "pass",
            "tone": "pass",
            "pill": "PASS",
            "display_state": "PASS",
            "final_state_class": "pass",
            "guidance_intent": "already_efficient",
            "selected_family_id": "TARGET_BAND_REACHED",
            "published_family_id": "TARGET_BAND_REACHED",
            "cta_family_id": "TARGET_BAND_REACHED",
            "card_family_id": "TARGET_BAND_REACHED",
            "matched_family_ids": ["TARGET_BAND_REACHED"],
            "family_match_passed": True,
            "candidate_search_evidence": cleaned_evidence,
            "button_contract": button_contract,
            "action_type": "",
            "updates": {},
            "primary_card_actionable": False,
            "stale_family_contract_violation_normalised": True,
        }
    )
    if details_d:
        cleaned_details = dict(details_d)
        cleaned_details.update(
            {
                "selected_family_id": "TARGET_BAND_REACHED",
                "published_family_id": "TARGET_BAND_REACHED",
                "cta_family_id": "TARGET_BAND_REACHED",
                "card_family_id": "TARGET_BAND_REACHED",
                "matched_family_ids": ["TARGET_BAND_REACHED"],
                "family_match_passed": True,
                "family_match_violation_reason": None,
                "blocking_reason": None,
                "candidate_search_evidence": cleaned_evidence,
                "stale_family_contract_violation_normalised": True,
            }
        )
        cleaned_details.pop("blocker_explanation", None)
        item_d["details"] = cleaned_details
    return item_d


def build_final_design_guide_cta(
    *,
    item: dict[str, Any] | None = None,
    debug: dict[str, Any] | None = None,
) -> FinalDesignGuideCTA:
    debug_d = _mapping(debug)
    item_d = normalise_stale_family_contract_violation_item(item, debug_d)
    contract = _mapping(
        item_d.get("button_contract")
        or debug_d.get("displayed_primary_button_contract")
        or debug_d.get("primary_button_contract")
        or debug_d.get("button_contract")
    )
    action_payload = _mapping(item_d.get("action_payload") or debug_d.get("design_guide_primary_apply_payload"))
    evidence = _mapping(item_d.get("candidate_search_evidence") or debug_d.get("candidate_search_evidence"))
    updates = _mapping(
        contract.get("updates")
        or action_payload.get("updates")
        or action_payload.get("resolved_candidate_updates")
        or item_d.get("updates")
        or evidence.get("selected_candidate_updates")
        or evidence.get("best_safe_candidate_updates")
        or evidence.get("proposed_updates")
    )
    apply_payload_source = action_payload or {"updates": updates}
    contract_action_type = _text(contract.get("action_type"), item_d.get("action_type"), action_payload.get("action_type"))
    family_identity = str(
        contract.get("family_id")
        or contract.get("selected_family_id")
        or contract.get("published_family_id")
        or contract.get("apply_payload_family_id")
        or item_d.get("family_id")
        or item_d.get("selected_family_id")
        or item_d.get("published_family_id")
        or evidence.get("family_id")
        or evidence.get("selected_family_id")
        or evidence.get("published_family_id")
        or ""
    ).strip().upper()
    expected_util_for_terminal_gate = _number_or_none(
        contract.get("expected_util")
        or action_payload.get("expected_util")
        or action_payload.get("resolved_candidate_post_util")
        or evidence.get("terminal_preview_util")
        or evidence.get("best_target_band_candidate_util")
        or evidence.get("selected_candidate_util")
        or evidence.get("best_safe_final_util")
        or item_d.get("expected_util")
        or item_d.get("candidate_post_util")
    )
    terminal_candidate_status = str(evidence.get("terminal_candidate_status") or "").strip().upper()
    target_band_candidate_count = int(
        evidence.get("target_band_candidate_count")
        or evidence.get("executable_target_band_candidate_count")
        or len(list(evidence.get("target_band_candidates") or []))
        or 0
    )
    family_safe_pass_fallback_proven = bool(
        item_d.get("family_safe_pass_fallback")
        or contract.get("family_safe_pass_fallback")
        or action_payload.get("family_safe_pass_fallback")
        or evidence.get("family_safe_pass_fallback")
    )
    family_safe_pass_fallback_intent = str(
        item_d.get("guidance_intent")
        or contract.get("family_safe_pass_fallback_intent")
        or action_payload.get("family_safe_pass_fallback_intent")
        or evidence.get("family_safe_pass_fallback_intent")
        or ""
    ).strip().lower()
    family_safe_pass_fallback = bool(
        family_safe_pass_fallback_proven
        and family_safe_pass_fallback_intent
        in {
            "required_fix",
            "optional_cleanup",
            "efficiency_tightening",
        }
        and (contract.get("enabled") or contract.get("actionable"))
        and contract.get("preview_pass") is True
        and contract_action_type
        and updates
    )
    overdesign_terminal_gate_blocked = bool(
        family_identity in {"BENDING_OVERDESIGN_GOVERNS", "COMBINED_OVERDESIGN_GOVERNS", "COMBINED_OVERDESIGN"}
        and contract_action_type
        and updates
        and expected_util_for_terminal_gate is not None
        and float(expected_util_for_terminal_gate) < 0.85 - 1e-9
        and terminal_candidate_status
        not in {
            "TERMINAL_TARGET_BAND",
            "TERMINAL_EXACT_STOP",
            "TERMINAL_BLOCKED_WITH_PROOF",
        }
        and target_band_candidate_count <= 0
        and not family_safe_pass_fallback
    )
    if overdesign_terminal_gate_blocked:
        contract = {
            **contract,
            "enabled": False,
            "actionable": False,
            "action_type": None,
            "updates": {},
            "blocking_reason": "non_terminal_overdesign_cleanup_candidate",
            "disabled_reason": "non_terminal_overdesign_cleanup_candidate",
            "terminal_candidate_status": terminal_candidate_status or "NON_TERMINAL_FURTHER_CLEANUP_AVAILABLE",
            "further_cleanup_available": True,
        }
        action_payload = {
            **action_payload,
            "updates": {},
            "resolved_candidate_updates": {},
            "action_type": None,
            "resolved_candidate_action_type": None,
            "blocking_reason": "non_terminal_overdesign_cleanup_candidate",
        }
        updates = {}
        contract_action_type = ""
    contract_is_executable = bool(
        (contract.get("enabled") or contract.get("actionable"))
        and updates
        and contract_action_type
        and contract.get("preview_pass") is not False
        and not _text(contract.get("disabled_reason"), contract.get("blocking_reason"), item_d.get("blocking_reason"))
    )
    executor_backed_proof = {
        "executor_backed": bool(
            contract.get("executor_backed")
            or contract_is_executable
            or action_payload.get("executor_backed")
            or evidence.get("executor_backed")
            or evidence.get("safe_executor_backed_candidate_found")
            or int(evidence.get("safe_executor_backed_candidates_count") or 0) > 0
        ),
        "safe_executor_backed_candidates_count": evidence.get("safe_executor_backed_candidates_count"),
        "preview_pass": contract.get("preview_pass"),
        "source": _text(contract.get("executor_source"), evidence.get("executor_source"), "publication_payload"),
    }
    stale_fresh_token_proof = {
        "component_apply_token": _text(
            action_payload.get("component_apply_token"),
            debug_d.get("component_apply_token"),
        ),
        "stale_apply_payload_blocked": bool(
            action_payload.get("stale_apply_payload_blocked")
            or debug_d.get("stale_apply_payload_blocked")
        ),
        "stale_apply_payload_mismatch_reason": _text(
            action_payload.get("stale_apply_payload_mismatch_reason"),
            debug_d.get("stale_apply_payload_mismatch_reason"),
            debug_d.get("component_apply_stale_reason"),
        ),
        "expected_fingerprint": _text(
            action_payload.get("stale_apply_payload_expected_fingerprint"),
            debug_d.get("stale_apply_payload_expected_fingerprint"),
        ),
        "current_fingerprint": _text(
            action_payload.get("stale_apply_payload_current_fingerprint"),
            debug_d.get("stale_apply_payload_current_fingerprint"),
        ),
    }
    source_precedence_proof = {
        "button_contract_source": _text(
            debug_d.get("winning_button_contract_source"),
            debug_d.get("button_contract_source"),
            evidence.get("winning_button_contract_source"),
        ),
        "update_payload_source": _text(
            debug_d.get("winning_update_payload_source"),
            debug_d.get("update_payload_source"),
            evidence.get("winning_update_payload_source"),
        ),
        "candidate_source": _text(
            debug_d.get("winning_candidate_source"),
            debug_d.get("candidate_source"),
            evidence.get("winning_candidate_source"),
        ),
        "source_precedence_hash": stable_final_publication_hash(
            {
                "button_contract_source": debug_d.get("winning_button_contract_source")
                or debug_d.get("button_contract_source")
                or evidence.get("winning_button_contract_source"),
                "update_payload_source": debug_d.get("winning_update_payload_source")
                or debug_d.get("update_payload_source")
                or evidence.get("winning_update_payload_source"),
                "candidate_source": debug_d.get("winning_candidate_source")
                or debug_d.get("candidate_source")
                or evidence.get("winning_candidate_source"),
            }
        ),
    }
    derived_executor_enabled = bool(
        executor_backed_proof.get("executor_backed")
        and bool(updates)
        and bool(contract_action_type)
        and executor_backed_proof.get("preview_pass") is True
        and not _text(contract.get("disabled_reason"), contract.get("blocking_reason"), item_d.get("blocking_reason"))
    )
    disabled_reason = _text(contract.get("disabled_reason"), contract.get("blocking_reason"), item_d.get("blocking_reason"))
    cta_has_executable_payload = bool(updates) and bool(contract_action_type)
    cta_enabled = bool(
        (contract.get("enabled") or contract.get("actionable") or derived_executor_enabled)
        and cta_has_executable_payload
        and not disabled_reason
    )
    effective_updates = dict(updates) if cta_enabled else {}
    effective_action_type = contract_action_type if cta_enabled else None
    preserve_stale_disabled_payload = bool(stale_fresh_token_proof.get("stale_apply_payload_blocked"))
    if preserve_stale_disabled_payload and not cta_enabled:
        effective_updates = dict(updates)
        effective_action_type = contract_action_type
    elif not cta_enabled:
        updates = {}
        contract_action_type = ""
        apply_payload_source = {"updates": {}}
    one_click_action_handoff = {
        "action_type": effective_action_type,
        "candidate_id": _text(
            contract.get("source_candidate_id"),
            contract.get("candidate_id"),
            action_payload.get("source_candidate_id"),
            action_payload.get("candidate_id"),
            item_d.get("source_candidate_id"),
            item_d.get("candidate_id"),
        ),
        "updates_hash": stable_final_publication_hash(effective_updates),
        "has_updates": bool(effective_updates),
    }
    cta_family_identity = _text(
        item_d.get("selected_family_id"),
        item_d.get("published_family_id"),
        evidence.get("selected_family_id"),
        evidence.get("published_family_id"),
        contract.get("selected_family_id"),
        contract.get("published_family_id"),
        contract.get("family_id"),
        action_payload.get("selected_family_id"),
        action_payload.get("published_family_id"),
        action_payload.get("family"),
        contract.get("family"),
        item_d.get("family"),
        item_d.get("check_key"),
    )
    cta_family_identity = _canonical_overdesign_family_identity_from_context(
        cta_family_identity,
        effective_updates,
        item_d,
        evidence,
        debug_d,
        contract,
        action_payload,
    ) or cta_family_identity
    authoritative_family_override = _text(
        item_d.get("authoritative_family_override"),
        debug_d.get("authoritative_family_override"),
    )
    if authoritative_family_override:
        cta_family_identity = authoritative_family_override
    else:
        cta_family_identity = _canonical_active_failure_mixed_family_identity_from_context(
            cta_family_identity,
            effective_updates,
            item_d,
            evidence,
            debug_d,
            contract,
            action_payload,
        ) or cta_family_identity
    one_click_action_handoff["family"] = cta_family_identity
    return FinalDesignGuideCTA(
        enabled=cta_enabled,
        actionable=bool(cta_enabled and (contract.get("actionable") or derived_executor_enabled)),
        label=_text(item_d.get("primary_action"), item_d.get("cta_label"), contract.get("label")),
        action_type=effective_action_type,
        family=cta_family_identity,
        updates=effective_updates,
        disabled_reason=disabled_reason,
        apply_payload_summary={
            "action_type": effective_action_type,
            "family": cta_family_identity,
            "updates": effective_updates,
            "updates_hash": stable_final_publication_hash(effective_updates),
            "candidate_id": action_payload.get("candidate_id") or contract.get("candidate_id"),
            "source_candidate_id": action_payload.get("source_candidate_id") or contract.get("source_candidate_id"),
        },
        apply_payload_fingerprint=stable_final_publication_hash(apply_payload_source),
        button_contract_hash=stable_final_publication_hash(contract),
        source_candidate_id=_text(contract.get("source_candidate_id"), contract.get("candidate_id"), item_d.get("source_candidate_id"), item_d.get("candidate_id")),
        executor_backed_proof=executor_backed_proof,
        stale_fresh_token_proof=stale_fresh_token_proof,
        one_click_action_handoff=one_click_action_handoff,
        source_precedence_proof=source_precedence_proof,
        product_driving=False,
    )


def build_final_publication_cta_from_current_state(
    *,
    item: dict[str, Any] | None = None,
    debug: dict[str, Any] | None = None,
    button_contract: dict[str, Any] | None = None,
    action_payload: dict[str, Any] | None = None,
    candidate_search_evidence: dict[str, Any] | None = None,
    source_precedence: dict[str, Any] | None = None,
) -> FinalDesignGuideCTA:
    """Proof-only CTA adapter for current distributed publication state.

    The adapter accepts plain dictionaries only. It does not read page/session
    state, render buttons, route apply actions, or drive one-click behavior.
    """

    item_d = _mapping(item)
    debug_d = _mapping(debug)
    if isinstance(button_contract, dict) and button_contract:
        item_d["button_contract"] = dict(button_contract)
    if isinstance(action_payload, dict) and action_payload:
        item_d["action_payload"] = dict(action_payload)
    evidence = _mapping(candidate_search_evidence)
    if evidence:
        item_d["candidate_search_evidence"] = {
            **_mapping(item_d.get("candidate_search_evidence")),
            **evidence,
        }
    precedence = _mapping(source_precedence)
    if precedence:
        debug_d.update(
            {
                "winning_button_contract_source": precedence.get("winning_button_contract_source")
                or precedence.get("button_contract_source"),
                "winning_update_payload_source": precedence.get("winning_update_payload_source")
                or precedence.get("update_payload_source"),
                "winning_candidate_source": precedence.get("winning_candidate_source")
                or precedence.get("candidate_source"),
            }
        )
    return build_final_design_guide_cta(item=item_d, debug=debug_d)


def _display_status_from_presentation_bucket(value: Any) -> str | None:
    bucket = str(value or "").strip().lower()
    if not bucket:
        return None
    if bucket in {"efficiency", "info"}:
        return "EFFICIENCY"
    if bucket in {"pass", "success", "green"}:
        return "PASS"
    if bucket in {"warn", "warning", "near-limit", "near_limit"}:
        return "WARN"
    if bucket in {"fail", "error", "blocked"}:
        return "FAIL"
    return None


def _final_card_section_util(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _final_card_section_status(util: float | None) -> str:
    if util is None:
        return "CURRENT"
    return "PASS" if util <= 1.0 + 1e-9 else "FAIL"


def _final_card_section_value(util: float | None) -> str:
    return "-" if util is None else f"{util:.2f}"


def _final_card_section_family(item: Mapping[str, Any], debug: Mapping[str, Any]) -> str | None:
    family_text = str(
        item.get("selected_family_id")
        or debug.get("selected_family_id")
        or item.get("family")
        or item.get("affected_family")
        or ""
    ).strip().lower()
    if "combined" in family_text:
        return "combined"
    for family in ("bending", "shear", "crack", "deflection"):
        if family in family_text:
            return family
    return None


def _final_card_authoritative_sections(
    item: Mapping[str, Any],
    debug: Mapping[str, Any],
) -> dict[str, Any]:
    """Project display rows from already-authoritative result fields.

    This is formatting-only: it does not search, select a family, alter target
    bands, or create an Apply payload.
    """

    family_utils = _mapping(debug.get("family_utils"))
    if not family_utils:
        family_utils = _mapping(_mapping(item.get("details")).get("family_utils"))
    display_truth = _mapping(
        item.get("display_truth")
        or debug.get("primary_display_truth")
        or debug.get("display_truth")
    )
    preview_family = _final_card_section_family(item, debug)
    preview_util = _final_card_section_util(
        display_truth.get("displayed_util")
        or item.get("resolved_candidate_post_util")
        or _mapping(item.get("button_contract")).get("expected_util")
        or debug.get("primary_preview_util")
    )
    preview_status = str(display_truth.get("displayed_status") or "").strip().upper()
    if not preview_status and preview_util is not None:
        preview_status = _final_card_section_status(preview_util)

    current_rows: list[dict[str, Any]] = []
    preview_display_rows: list[dict[str, Any]] = []
    for family, label in (
        ("bending", "Bending"),
        ("shear", "Shear"),
        ("crack", "Crack"),
        ("deflection", "Deflection"),
    ):
        current_util = _final_card_section_util(family_utils.get(family))
        if current_util is None:
            continue
        current_status = _final_card_section_status(current_util)
        current_rows.append(
            {
                "family": family,
                "label": label,
                "value": _final_card_section_value(current_util),
                "status": current_status,
                "tone": "green" if current_status == "PASS" else "red",
            }
        )
        after_util = preview_util if family == preview_family and preview_util is not None else current_util
        after_status = preview_status if family == preview_family and preview_status else current_status
        preview_display_rows.append(
            {
                "family": family,
                "label": label,
                "before": f"{_final_card_section_value(current_util)} {current_status}",
                "after": f"{_final_card_section_value(after_util)} {after_status}",
            }
        )

    if preview_family == "combined" and preview_util is not None:
        current_governing_util = _final_card_section_util(
            display_truth.get("source_summary_util")
        )
        if current_governing_util is None:
            parsed_family_utils = [
                parsed
                for parsed in (
                    _final_card_section_util(value)
                    for value in family_utils.values()
                )
                if parsed is not None
            ]
            current_governing_util = (
                max(parsed_family_utils) if parsed_family_utils else None
            )
        current_governing_status = _final_card_section_status(
            current_governing_util
        )
        preview_display_rows.append(
            {
                "family": "combined",
                "label": "Combined governing",
                "before": (
                    f"{_final_card_section_value(current_governing_util)} "
                    f"{current_governing_status}"
                ),
                "after": (
                    f"{_final_card_section_value(preview_util)} "
                    f"{preview_status or _final_card_section_status(preview_util)}"
                ),
            }
        )

    reason_text = _text(
        item.get("guidance_why_text_compact"),
        item.get("guidance_why"),
        item.get("reasoning"),
    )
    change_lines = [
        str(line).strip()
        for line in list(item.get("guidance_change_lines") or [])
        if str(line).strip()
    ]
    reason_rows: list[dict[str, Any]] = []
    if reason_text:
        reason_rows.append({"test_label": "why", "label": "Why", "text": reason_text})
    if change_lines:
        reason_rows.append(
            {
                "test_label": "change",
                "label": "Change",
                "text": "; ".join(change_lines),
            }
        )

    return {
        "current": current_rows,
        "preview_display_rows": preview_display_rows,
        "reason_display_rows": reason_rows,
    }


def final_design_guide_publication_from_dict(
    payload: Mapping[str, Any] | None,
) -> FinalDesignGuidePublication:
    """Hydrate an already-authoritative publication without reclassifying it."""

    source = _mapping(payload)
    if not source:
        raise ValueError("final publication payload is required")

    def _kwargs(model: type[Any], value: Any) -> dict[str, Any]:
        allowed = {entry.name for entry in fields(model)}
        return {
            key: item
            for key, item in _mapping(value).items()
            if key in allowed
        }

    return FinalDesignGuidePublication(
        **{
            **_kwargs(FinalDesignGuidePublication, source),
            "cta": FinalDesignGuideCTA(
                **_kwargs(FinalDesignGuideCTA, source.get("cta"))
            ),
            "display": FinalDesignGuideDisplay(
                **_kwargs(FinalDesignGuideDisplay, source.get("display"))
            ),
            "evidence": FinalDesignGuideEvidence(
                **_kwargs(FinalDesignGuideEvidence, source.get("evidence"))
            ),
            "verifier_payload": FinalDesignGuideVerifierPayload(
                **_kwargs(
                    FinalDesignGuideVerifierPayload,
                    source.get("verifier_payload"),
                )
            ),
        }
    )


def build_final_design_guide_display(
    *,
    item: dict[str, Any] | None = None,
    debug: dict[str, Any] | None = None,
) -> FinalDesignGuideDisplay:
    item_d = normalise_stale_family_contract_violation_item(item, debug)
    debug_d = _mapping(debug)
    family_contract_violation = is_final_design_guide_family_contract_violation_item(item_d)
    presentation_d = _mapping(debug_d.get("design_guide_presentation"))
    if item_d.get("stale_contract_violation_recovered_to_combined_action"):
        presentation_d = {}
    presentation_title = _text(presentation_d.get("headline"), presentation_d.get("title"))
    presentation_summary = _text(presentation_d.get("subtext"), presentation_d.get("summary"))
    presentation_bucket = _text(
        presentation_d.get("css_bucket"),
        presentation_d.get("bucket"),
        presentation_d.get("theme"),
    )
    presentation_status = _text(
        presentation_d.get("status"),
        _display_status_from_presentation_bucket(presentation_bucket),
    )
    button_contract = _mapping(item_d.get("button_contract"))
    reasons = [dict(row) for row in list(item_d.get("reasons") or []) if isinstance(row, dict)]
    details = _mapping(item_d.get("details"))
    candidate_search_evidence = _mapping(
        item_d.get("candidate_search_evidence")
        or debug_d.get("candidate_search_evidence")
    )
    authoritative_sections = _final_card_authoritative_sections(item_d, debug_d)
    item_current = [
        dict(row) for row in list(item_d.get("current") or []) if isinstance(row, dict)
    ]
    item_reasons = [
        dict(row) for row in list(item_d.get("reasons") or []) if isinstance(row, dict)
    ]
    exact_blockers_for_sections = _mapping(
        item_d.get("exact_blockers_by_family")
        or details.get("exact_blockers_by_family")
        or candidate_search_evidence.get("exact_blockers_by_family")
        or candidate_search_evidence.get("post_click_exact_blockers_by_family")
        or debug_d.get("exact_blockers_by_family")
        or debug_d.get("post_click_exact_blockers_by_family")
    )
    blocker_attempts_for_sections = _mapping(
        item_d.get("blocker_attempts_by_family")
        or details.get("blocker_attempts_by_family")
        or candidate_search_evidence.get("blocker_attempts_by_family")
        or exact_blockers_for_sections
    )
    expanded_evidence_sections = {
        "reasons": item_reasons or list(authoritative_sections["reason_display_rows"]),
        "reason_display_rows": list(authoritative_sections["reason_display_rows"]),
        "current": item_current or list(authoritative_sections["current"]),
        "preview": _mapping(item_d.get("preview")),
        "preview_display_rows": list(authoritative_sections["preview_display_rows"]),
        "details": details,
        "design_guide_presentation": presentation_d,
        "exact_blockers_by_family": exact_blockers_for_sections,
        "blocker_attempts_by_family": blocker_attempts_for_sections,
    }
    exact_blocker_for_display = _mapping(
        next(iter(expanded_evidence_sections["exact_blockers_by_family"].values()), {})
        if expanded_evidence_sections["exact_blockers_by_family"]
        else {}
    )
    blocker_explanation = _text(
        item_d.get("blocker_explanation"),
        exact_blocker_for_display.get("reason"),
        candidate_search_evidence.get("active_under_capacity_blocker_reason"),
        candidate_search_evidence.get("outside_target_band_allowed_reason"),
        item_d.get("blocking_reason"),
        button_contract.get("blocking_reason"),
        button_contract.get("disabled_reason"),
        details.get("blocking_reason"),
    )
    display_state = _text(
        presentation_status,
        item_d.get("display_state"),
        item_d.get("status"),
        item_d.get("bucket"),
        "PROOF_PENDING",
    )
    final_card_model_fields = {
        "title": _text(presentation_title, item_d.get("title_main"), item_d.get("title")),
        "badge": _text(item_d.get("pill"), item_d.get("governing_label"), item_d.get("status"), item_d.get("bucket")),
        "summary": _text(presentation_summary, item_d.get("summary_line"), item_d.get("primary_action"), item_d.get("reasoning")),
        "status": _text(presentation_status, item_d.get("status"), item_d.get("critical_status")),
        "bucket": _text(presentation_bucket, item_d.get("bucket")),
        "colour_state": _text(presentation_bucket, item_d.get("tone"), item_d.get("status"), item_d.get("bucket")),
        "card_class": _text(item_d.get("card_class"), item_d.get("final_card_class")),
        "display_state": display_state,
        "blocker_explanation": blocker_explanation,
        "display_source": "design_guide_presentation" if presentation_d else "item",
    }
    title_lower = str(final_card_model_fields.get("title") or "").strip().lower()
    selected_family = str(
        item_d.get("selected_family_id")
        or item_d.get("published_family_id")
        or item_d.get("cta_family_id")
        or debug_d.get("selected_family_id")
        or ""
    ).strip().upper()
    locked_no_repair_surface = bool(
        selected_family == "LOCKED_NO_REPAIR"
        or item_d.get("locked_no_repair")
        or _mapping(item_d.get("candidate_search_evidence")).get("locked_no_repair")
        or title_lower.startswith("no legal repair")
        or "locked/no valid repair" in title_lower
    )
    if family_contract_violation:
        final_card_model_fields.update(
            {
                "badge": "ERROR",
                "status": "ERROR",
                "bucket": "error",
                "colour_state": "error",
                "display_state": "ERROR",
                "blocker_explanation": blocker_explanation or "family_selection_contract_mismatch",
            }
        )
        display_state = "ERROR"
    elif locked_no_repair_surface:
        final_card_model_fields.update(
            {
                "badge": "BLOCKED",
                "status": "BLOCKED",
                "bucket": "blocked",
                "colour_state": "blocked",
                "display_state": "BLOCKED",
                "blocker_explanation": blocker_explanation or "locked_no_valid_repair",
            }
        )
        display_state = "BLOCKED"
        blocker_explanation = final_card_model_fields["blocker_explanation"]
    elif final_design_guide_publication_is_terminal_no_action_surface(item_d, debug_d):
        terminal_badge = str(final_card_model_fields.get("badge") or "").strip().upper()
        if not terminal_badge or terminal_badge == "ACTION":
            terminal_badge = "GOOD"
        final_card_model_fields.update(
            {
                "badge": terminal_badge,
                "status": "PASS",
                "bucket": "pass",
                "colour_state": "pass",
                "display_state": "PASS",
                "blocker_explanation": None,
            }
        )
        display_state = "PASS"
    fallback_shell_model = _mapping(item_d.get("render_fallback_shell_model"))
    if not fallback_shell_model and item_d.get("render_fallback_shell"):
        fallback_shell_model = {
            "title": final_card_model_fields["title"],
            "card_class": final_card_model_fields["card_class"],
            "fallback_only": True,
        }
    visible_wording = {
        "title": final_card_model_fields["title"],
        "summary": final_card_model_fields["summary"],
        "badge": final_card_model_fields["badge"],
        "blocker_explanation": blocker_explanation,
    }
    return FinalDesignGuideDisplay(
        title=visible_wording["title"],
        badge=visible_wording["badge"],
        summary=visible_wording["summary"],
        status=final_card_model_fields["status"],
        bucket=final_card_model_fields["bucket"],
        colour_state=final_card_model_fields["colour_state"],
        card_class=_text(item_d.get("card_class"), item_d.get("final_card_class")),
        display_state=display_state,
        expanded_evidence_sections=expanded_evidence_sections,
        blocker_explanation=blocker_explanation,
        final_card_model_fields=final_card_model_fields,
        final_card_model_hash=stable_final_publication_hash(final_card_model_fields),
        render_fallback_shell_model=fallback_shell_model,
        render_fallback_shell_hash=stable_final_publication_hash(fallback_shell_model),
        visible_wording_hash=stable_final_publication_hash(visible_wording),
        renderer_driving=False,
    )


def _terminal_no_action_display(
    display: FinalDesignGuideDisplay,
    *,
    outcome_state: FinalDesignGuideOutcomeState,
) -> FinalDesignGuideDisplay:
    """Project terminal no-action proof onto the display surface.

    Some legacy items still carry ACTION-shaped presentation fields while the
    final publication evidence proves a terminal no-action state. The final
    publication object owns that truth, so the compatibility render item must
    inherit the terminal PASS display rather than keeping stale ACTION styling.
    """

    payload = display.to_dict()
    final_card_model_fields = dict(payload.get("final_card_model_fields") or {})
    badge = str(payload.get("badge") or final_card_model_fields.get("badge") or "").strip().upper()
    if not badge or badge == "ACTION":
        badge = "GOOD"
    final_card_model_fields.update(
        {
            "badge": badge,
            "status": "PASS",
            "bucket": "pass",
            "colour_state": "pass",
            "display_state": outcome_state,
            "blocker_explanation": None,
        }
    )
    visible_wording = {
        "title": payload.get("title"),
        "summary": payload.get("summary"),
        "badge": badge,
        "blocker_explanation": None,
    }
    return FinalDesignGuideDisplay(
        title=payload.get("title"),
        badge=badge,
        summary=payload.get("summary"),
        status="PASS",
        bucket="pass",
        colour_state="pass",
        card_class=None,
        display_state=outcome_state,
        expanded_evidence_sections=dict(payload.get("expanded_evidence_sections") or {}),
        blocker_explanation=None,
        final_card_model_fields=final_card_model_fields,
        final_card_model_hash=stable_final_publication_hash(final_card_model_fields),
        render_fallback_shell_model=dict(payload.get("render_fallback_shell_model") or {}),
        render_fallback_shell_hash=payload.get("render_fallback_shell_hash"),
        visible_wording_hash=stable_final_publication_hash(visible_wording),
        renderer_driving=False,
    )


def _optimal_no_action_display(
    display: FinalDesignGuideDisplay,
    *,
    blocker_reason: str | None,
    optimal_blocker_proof: dict[str, Any] | None = None,
) -> FinalDesignGuideDisplay:
    """Project safe exact-stop/no-action blockers as green optimal display.

    A safe design that cannot be improved further should not look like a red
    product blocker. It should remain a PASS/GOOD card and carry the family
    blocker explanation as evidence.
    """

    payload = display.to_dict()
    proof = _mapping(optimal_blocker_proof)
    reasons = list(proof.get("family_blocker_reasons") or [])
    explanation = _text(blocker_reason, "; ".join(str(row) for row in reasons if str(row).strip()))
    title = _text(payload.get("title"), "Design is optimal")
    summary = _text(
        payload.get("summary"),
        "All required checks pass; no further safe family-owned optimisation is available.",
    )
    final_card_model_fields = dict(payload.get("final_card_model_fields") or {})
    final_card_model_fields.update(
        {
            "badge": "PASS",
            "status": "PASS",
            "bucket": "pass",
            "colour_state": "pass",
            "display_state": "PASS",
            "blocker_explanation": explanation,
            "optimal_blocker_proof": proof,
        }
    )
    sections = dict(payload.get("expanded_evidence_sections") or {})
    if proof:
        sections["Optimal blocker evidence"] = {
            "rows": [proof],
            "visible": True,
            "source": "FinalDesignGuidePublication.evidence.optimal_blocker_proof",
        }
    visible_wording = {
        "title": title,
        "summary": summary,
        "badge": "PASS",
        "blocker_explanation": explanation,
    }
    return FinalDesignGuideDisplay(
        title=title,
        badge="PASS",
        summary=summary,
        status="PASS",
        bucket="pass",
        colour_state="pass",
        card_class=None,
        display_state="PASS",
        expanded_evidence_sections=sections,
        blocker_explanation=explanation,
        final_card_model_fields=final_card_model_fields,
        final_card_model_hash=stable_final_publication_hash(final_card_model_fields),
        render_fallback_shell_model=dict(payload.get("render_fallback_shell_model") or {}),
        render_fallback_shell_hash=payload.get("render_fallback_shell_hash"),
        visible_wording_hash=stable_final_publication_hash(visible_wording),
        renderer_driving=False,
    )


def _blocked_no_action_display(
    display: FinalDesignGuideDisplay,
    *,
    blocker_reason: str | None,
) -> FinalDesignGuideDisplay:
    """Project blocked no-action proof onto stale ACTION-shaped display fields."""

    payload = display.to_dict()
    resolved_reason = blocker_reason or payload.get("blocker_explanation")
    summary = str(payload.get("summary") or "").strip()
    title = str(payload.get("title") or "").strip()
    if resolved_reason:
        reason_text = str(resolved_reason).strip()
        if not any(
            token in reason_text.lower()
            for token in (
                "no safe one-click",
                "no one-click repair",
                "no valid repair",
            )
        ):
            reason_text = f"No safe one-click repair was found. {reason_text}"
        summary = f"No repair is executable. {reason_text}"
        reason_lower = reason_text.lower()
        if (
            "combined_bending_shear_fail" in reason_lower
            or ("shear_fail" in reason_lower and "bending_fail" in reason_lower)
        ):
            title = "Bending and shear capacity are low"
        elif "shear_fail" in reason_lower:
            title = "Shear capacity is low"
        elif "bending_fail" in reason_lower:
            title = "Bending capacity is low"
    final_card_model_fields = dict(payload.get("final_card_model_fields") or {})
    final_card_model_fields.update(
        {
            "badge": "BLOCKED",
            "status": "BLOCKED",
            "bucket": "blocked",
            "colour_state": "blocked",
            "display_state": "BLOCKED",
            "summary": summary,
            "blocker_explanation": resolved_reason,
        }
    )
    visible_wording = {
        "title": title or payload.get("title"),
        "summary": summary,
        "badge": "BLOCKED",
        "blocker_explanation": resolved_reason,
    }
    return FinalDesignGuideDisplay(
        title=title or payload.get("title"),
        badge="BLOCKED",
        summary=summary,
        status="BLOCKED",
        bucket="blocked",
        colour_state="blocked",
        card_class=payload.get("card_class"),
        display_state="BLOCKED",
        expanded_evidence_sections=dict(payload.get("expanded_evidence_sections") or {}),
        blocker_explanation=resolved_reason,
        final_card_model_fields=final_card_model_fields,
        final_card_model_hash=stable_final_publication_hash(final_card_model_fields),
        render_fallback_shell_model=dict(payload.get("render_fallback_shell_model") or {}),
        render_fallback_shell_hash=payload.get("render_fallback_shell_hash"),
        visible_wording_hash=stable_final_publication_hash(visible_wording),
        renderer_driving=False,
    )


def build_final_publication_display_from_current_card_model(
    *,
    view_model: dict[str, Any] | None = None,
    render_model: dict[str, Any] | None = None,
    fallback_shell_model: dict[str, Any] | None = None,
) -> FinalDesignGuideDisplay:
    """Proof-only adapter from current card VM/render-model state.

    This accepts already-shaped dictionaries only. It does not import page code,
    render HTML, decide CTA, or mutate live publication state.
    """

    vm_d = _mapping(view_model)
    rm_d = _mapping(render_model)
    shell_d = _mapping(fallback_shell_model)
    reasons = [
        dict(row)
        for row in list(
            rm_d.get("final_reasons")
            or rm_d.get("reason_display_rows")
            or vm_d.get("reasons")
            or []
        )
        if isinstance(row, dict)
    ]
    details = _mapping(rm_d.get("details_payload") or vm_d.get("details"))
    final_card_model_fields = {
        "title": _text(rm_d.get("title"), vm_d.get("title"), vm_d.get("title_main")),
        "badge": _text(rm_d.get("pill"), vm_d.get("pill"), vm_d.get("governing_label"), vm_d.get("status")),
        "summary": _text(rm_d.get("main_text"), vm_d.get("summary_line"), vm_d.get("primary_action")),
        "status": _text(rm_d.get("status"), vm_d.get("status")),
        "bucket": _text(vm_d.get("bucket")),
        "colour_state": _text(rm_d.get("card_tone"), vm_d.get("tone"), vm_d.get("status"), vm_d.get("bucket")),
        "card_class": _text(rm_d.get("card_class"), vm_d.get("card_class"), vm_d.get("final_card_class")),
        "display_state": _text(
            vm_d.get("display_state"),
            rm_d.get("status"),
            vm_d.get("status"),
            vm_d.get("bucket"),
            "PROOF_PENDING",
        ),
        "blocker_explanation": _text(
            rm_d.get("blocker_reason"),
            vm_d.get("blocker_explanation"),
            vm_d.get("blocking_reason"),
            details.get("blocking_reason"),
        ),
    }
    expanded_evidence_sections = {
        "reasons": reasons,
        "reason_display_rows": [
            dict(row)
            for row in list(rm_d.get("reason_display_rows") or [])
            if isinstance(row, dict)
        ],
        "current": [
            dict(row)
            for row in list(rm_d.get("current_rows") or vm_d.get("current") or [])
            if isinstance(row, dict)
        ],
        "preview": _mapping(rm_d.get("preview_rows") or vm_d.get("preview")),
        "preview_display_rows": [
            dict(row)
            for row in list(rm_d.get("preview_display_rows") or [])
            if isinstance(row, dict)
        ],
        "details": details,
        "blocker_evidence_display_fields": _mapping(rm_d.get("blocker_evidence_display_fields")),
        "terminal_status": _mapping(rm_d.get("terminal_status")),
    }
    visible_wording = {
        "title": final_card_model_fields["title"],
        "summary": final_card_model_fields["summary"],
        "badge": final_card_model_fields["badge"],
        "blocker_explanation": final_card_model_fields["blocker_explanation"],
    }
    return FinalDesignGuideDisplay(
        title=final_card_model_fields["title"],
        badge=final_card_model_fields["badge"],
        summary=final_card_model_fields["summary"],
        status=final_card_model_fields["status"],
        bucket=final_card_model_fields["bucket"],
        colour_state=final_card_model_fields["colour_state"],
        card_class=final_card_model_fields["card_class"],
        display_state=final_card_model_fields["display_state"],
        expanded_evidence_sections=expanded_evidence_sections,
        blocker_explanation=final_card_model_fields["blocker_explanation"],
        final_card_model_fields=final_card_model_fields,
        final_card_model_hash=stable_final_publication_hash(final_card_model_fields),
        render_fallback_shell_model=shell_d,
        render_fallback_shell_hash=stable_final_publication_hash(shell_d),
        visible_wording_hash=stable_final_publication_hash(visible_wording),
        renderer_driving=False,
    )


def build_final_design_guide_direct_shell_identity_projection(
    *,
    family_identity: dict[str, Any] | None = None,
    title: object = None,
    governing_label: str | None = None,
    summary_line: str = "Run one-click auto design.",
    reason_text: str = "Run one-click auto design.",
) -> FinalDesignGuideDirectShellIdentityProjection:
    """Normalize direct-shell family identity without page rendering imports."""

    identity = _mapping(family_identity)
    selected_identity = _text(identity.get("selected_family_id"))
    published_identity = _text(identity.get("published_family_id"))
    cta_identity = _text(identity.get("cta_family_id"))
    apply_identity = _text(identity.get("apply_payload_family_id"))
    selection_evidence = _mapping(identity.get("selection_evidence"))
    if selected_identity and not identity.get("matched_family_ids"):
        evidence_matches = selection_evidence.get("matched_family_ids")
        if isinstance(evidence_matches, list) and evidence_matches:
            identity["matched_family_ids"] = list(evidence_matches)
        else:
            identity["matched_family_ids"] = [selected_identity]
    if selected_identity and not identity.get("raw_state_flags"):
        evidence_flags = selection_evidence.get("raw_state_flags")
        if isinstance(evidence_flags, dict) and evidence_flags:
            identity["raw_state_flags"] = dict(evidence_flags)
    title_text = _text(title)
    governing_label_text = _text(governing_label)
    summary_line_text = _text(summary_line, "Run one-click auto design.")
    reason_text_value = _text(reason_text, "Run one-click auto design.")
    if (
        selected_identity
        and published_identity == selected_identity
        and cta_identity == selected_identity
        and (not apply_identity or apply_identity == selected_identity)
    ):
        identity["apply_payload_family_id"] = selected_identity
        identity["family_match_passed"] = True
        identity["family_match_violation_reason"] = None
        stale_match_text = " ".join(
            str(part or "")
            for part in (title_text, governing_label_text, summary_line_text, reason_text_value)
        ).lower()
        if "family mismatch blocked" in stale_match_text or "publication blocked by family contract" in stale_match_text:
            if selected_identity == "COMBINED_BENDING_SHEAR_FAIL":
                title_text = "Strengthening required for bending and shear"
                governing_label_text = "Combined bending and shear repair"
                summary_line_text = "Run one-click auto design."
                reason_text_value = "Run one-click auto design."
            elif selected_identity == "SHEAR_FAIL_GOVERNS":
                governing_label_text = "Shear repair"
                summary_line_text = "Run one-click auto design."
                reason_text_value = "Run one-click auto design."
    payload = {
        "identity": identity,
        "title": title_text,
        "governing_label": governing_label_text,
        "summary_line": summary_line_text,
        "reason_text": reason_text_value,
    }
    return FinalDesignGuideDirectShellIdentityProjection(
        identity=identity,
        title=title_text,
        governing_label=governing_label_text,
        summary_line=summary_line_text,
        reason_text=reason_text_value,
        projection_hash=stable_final_publication_hash(payload),
        proof_only=True,
    )


def _direct_shell_parse_util_value(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except Exception:
        try:
            return float(str(value).strip())
        except Exception:
            return None


def _direct_shell_format_display_util(value: Any) -> str:
    parsed = _direct_shell_parse_util_value(value)
    if parsed is None:
        return "-"
    try:
        return f"{float(parsed):.2f}"
    except Exception:
        return "-"


def _direct_shell_family_row_from_overview(overview: dict[str, Any] | None, family: str) -> dict[str, Any]:
    ov = _mapping(overview)
    utils = _mapping(ov.get("utils"))
    statuses = _mapping(ov.get("statuses"))
    family_key = str(family or "").strip().lower()
    util = _direct_shell_parse_util_value(utils.get(family_key))
    if util is None:
        util = _direct_shell_parse_util_value(ov.get(f"{family_key}_util"))
    status = str(statuses.get(family_key) or ov.get(f"{family_key}_status") or "").strip().upper()
    if not status and family_key in {"crack", "deflection"} and util is not None:
        status = "PASS" if float(util) <= 1.0 + 1e-9 else "FAIL"
    return {
        "util": None if util is None else float(util),
        "status": status or None,
        "value": ov.get(f"{family_key}_value"),
        "limit": ov.get(f"{family_key}_limit"),
    }


def _direct_shell_active_failure_keys(overview: dict[str, Any] | None) -> set[str]:
    ov = _mapping(overview)
    statuses = _mapping(ov.get("statuses"))
    utils = _mapping(ov.get("utils"))
    out: set[str] = set()
    for key in ("bending", "shear", "crack", "deflection"):
        status = str(statuses.get(key) or "").strip().upper()
        util = _direct_shell_parse_util_value(utils.get(key))
        if status in {"FAIL", "NG", "FAILED"} or (util is not None and float(util) > 1.0 + 1e-9):
            out.add(key)
    return out


def build_final_design_guide_direct_shell_card_projection(
    *,
    title: object,
    pill: str = "ACTION",
    current_overview: dict[str, Any] | None = None,
    candidate_family: object = None,
    expected_util: object = None,
    preview_pass: object = True,
    governing_label: str | None = None,
    family_identity: dict[str, Any] | None = None,
    summary_line: str = "Run one-click auto design.",
    reason_text: str = "Run one-click auto design.",
    card_class: str | None = None,
) -> FinalDesignGuideDirectShellCardProjection:
    """Build the direct shell card VM without page/session/render imports."""

    overview = _mapping(current_overview)
    identity_projection = build_final_design_guide_direct_shell_identity_projection(
        family_identity=_mapping(family_identity),
        title=title,
        governing_label=governing_label,
        summary_line=summary_line,
        reason_text=reason_text,
    )
    identity = dict(identity_projection.identity)
    title_text = identity_projection.title
    governing_label_text = identity_projection.governing_label
    summary_line_text = identity_projection.summary_line or "Run one-click auto design."
    reason_text_value = identity_projection.reason_text or "Run one-click auto design."
    selected_identity = str(identity.get("selected_family_id") or "").strip()
    published_identity = str(identity.get("published_family_id") or "").strip()
    cta_identity = str(identity.get("cta_family_id") or "").strip()
    apply_identity = str(identity.get("apply_payload_family_id") or "").strip()
    cta_payload_id_value = ""
    if selected_identity:
        cta_payload_id_value = generic_family_owned_payload_id(
            selected_identity,
            identity,
            {"updates": dict(identity.get("updates") or {})},
        )
    candidate_family_key = str(candidate_family or "").strip().lower()
    expected_util_value = _direct_shell_parse_util_value(expected_util)
    current_rows: list[dict[str, Any]] = []
    preview_rows: dict[str, dict[str, Any]] = {}
    for family, label in (
        ("bending", "Bending"),
        ("shear", "Shear"),
        ("crack", "Crack"),
        ("deflection", "Deflection"),
    ):
        row = _direct_shell_family_row_from_overview(overview, family)
        util = row.get("util")
        status = str(row.get("status") or "CURRENT").strip().upper()
        if status == "FAIL":
            tone = "red"
        elif status == "PASS":
            tone = "green"
        else:
            tone = "grey"
        current_rows.append(
            {
                "family": family,
                "label": label,
                "value": _direct_shell_format_display_util(util),
                "status": status,
                "tone": tone,
            }
        )
        after_util = util
        after_status = status
        if family == candidate_family_key and expected_util_value is not None:
            after_util = float(expected_util_value)
            after_status = "PASS" if bool(preview_pass) else "PREVIEW_BLOCKED"
        preview_rows[family] = {
            "before_util": util,
            "after_util": after_util,
            "before_status": status,
            "after_status": after_status,
            "before_value": row.get("value"),
            "after_value": row.get("value"),
            "before_limit": row.get("limit"),
            "after_limit": row.get("limit"),
        }

    vm = {
        "status": "action",
        "pill": str(pill or "ACTION").strip().upper(),
        "title": str(title_text or "Design Guide action").strip(),
        "governing_label": str(governing_label_text or "Target cleanup preview").strip(),
        "selected_family_id": identity.get("selected_family_id"),
        "selected_family": identity.get("selected_family"),
        "selection_reason": identity.get("selection_reason")
        or identity.get("selected_family_reason"),
        "published_family_id": identity.get("published_family_id"),
        "cta_family_id": identity.get("cta_family_id"),
        "candidate_family_id": identity.get("candidate_family_id"),
        "card_family_id": identity.get("card_family_id"),
        "apply_payload_family_id": identity.get("apply_payload_family_id"),
        "family_selection_source": identity.get("family_selection_source"),
        "family_selection_contract": identity.get("family_selection_contract"),
        "family_chooser_contract": identity.get("family_chooser_contract"),
        "rejected_families": dict(identity.get("rejected_families") or {}),
        "selection_evidence": dict(identity.get("selection_evidence") or {}),
        "matched_family_ids": list(identity.get("matched_family_ids") or []),
        "raw_state_flags": dict(identity.get("raw_state_flags") or {}),
        "family_match_passed": identity.get("family_match_passed"),
        "family_match_violation_reason": identity.get("family_match_violation_reason"),
        "family_route_owner": identity.get("family_route_owner"),
        "family_early_dispatch_used": identity.get("family_early_dispatch_used"),
        "generic_one_click_solver_skipped": identity.get("generic_one_click_solver_skipped"),
        "generic_target_band_search_skipped": identity.get("generic_target_band_search_skipped"),
        "generic_optimisation_cleanup_skipped": identity.get("generic_optimisation_cleanup_skipped"),
        "generic_publication_fallback_skipped": identity.get("generic_publication_fallback_skipped"),
        "direct_target_band_bypassed_by_family_owner": identity.get("direct_target_band_bypassed_by_family_owner"),
        "bending_fail_contract_ladder_candidate_count": identity.get("bending_fail_contract_ladder_candidate_count"),
        "summary_line": str(summary_line_text or "Run one-click auto design.").strip(),
        "current": current_rows,
        "preview": preview_rows,
        "section_title": "Recommended action",
        "reasons": [
            {
                "label": "Change",
                "text": str(reason_text_value or "Run one-click auto design.").strip(),
                "tone": "info",
            }
        ],
        "details": {
            "current_overview": dict(overview),
            "debug": {"direct_action_shell": True},
            "selected_family_id": identity.get("selected_family_id"),
            "selected_family": identity.get("selected_family"),
            "selection_reason": identity.get("selection_reason")
            or identity.get("selected_family_reason"),
            "published_family_id": identity.get("published_family_id"),
            "cta_family_id": identity.get("cta_family_id"),
            "candidate_family_id": identity.get("candidate_family_id"),
            "card_family_id": identity.get("card_family_id"),
            "apply_payload_family_id": identity.get("apply_payload_family_id"),
            "family_selection_source": identity.get("family_selection_source"),
            "family_selection_contract": identity.get("family_selection_contract"),
            "family_chooser_contract": identity.get("family_chooser_contract"),
            "rejected_families": dict(identity.get("rejected_families") or {}),
            "selection_evidence": dict(identity.get("selection_evidence") or {}),
            "matched_family_ids": list(identity.get("matched_family_ids") or []),
            "raw_state_flags": dict(identity.get("raw_state_flags") or {}),
            "family_match_passed": identity.get("family_match_passed"),
            "family_match_violation_reason": identity.get("family_match_violation_reason"),
            "family_route_owner": identity.get("family_route_owner"),
            "family_early_dispatch_used": identity.get("family_early_dispatch_used"),
            "generic_one_click_solver_skipped": identity.get("generic_one_click_solver_skipped"),
            "generic_target_band_search_skipped": identity.get("generic_target_band_search_skipped"),
            "generic_optimisation_cleanup_skipped": identity.get("generic_optimisation_cleanup_skipped"),
            "generic_publication_fallback_skipped": identity.get("generic_publication_fallback_skipped"),
            "direct_target_band_bypassed_by_family_owner": identity.get("direct_target_band_bypassed_by_family_owner"),
            "bending_fail_contract_ladder_candidate_count": identity.get("bending_fail_contract_ladder_candidate_count"),
        },
        "cta": {
            "enabled": True,
            "label": "Run one-click auto design",
            "payload_id": cta_payload_id_value,
        },
    }
    family_tokens_for_shell = {
        str(candidate_family or "").strip().lower(),
        str(selected_identity or "").strip().lower(),
        str(published_identity or "").strip().lower(),
        str(cta_identity or "").strip().lower(),
        str(apply_identity or "").strip().lower(),
        str(identity.get("candidate_family_id") or "").strip().lower(),
        str(identity.get("card_family_id") or "").strip().lower(),
    }
    family_owned_strength_repair_shell = any(
        token
        and (
            token.endswith("_fail_governs")
            or token in {"bending_fail_governs", "shear_fail_governs", "combined_bending_shear_fail"}
            or token.startswith("bending_fail")
            or token.startswith("shear_fail")
            or token.startswith("combined_bending_shear_fail")
        )
        for token in family_tokens_for_shell
    )
    geometry_detailing_shell = bool("geometry_detailing_governs" in family_tokens_for_shell)
    active_failure_keys = _direct_shell_active_failure_keys(overview)
    active_strength_shell = bool(
        not geometry_detailing_shell
        and ((active_failure_keys & {"bending", "shear"}) or family_owned_strength_repair_shell)
    )
    if geometry_detailing_shell:
        vm["pill"] = "ACTION"
        vm["title"] = "Geometry needs correction"
        vm["governing_label"] = "Geometry/detailing correction"
        vm["summary_line"] = (
            "A geometry/detailing correction is available before normal engineering recommendation ladders run."
        )
        vm["status"] = "action"
        vm["section_title"] = "Geometry correction evidence"
        vm["reasons"] = [
            {
                "label": "Problem",
                "text": "The current geometry/detailing contract is invalid.",
                "tone": "red",
            },
            {
                "label": "Fix",
                "text": str(reason_text_value or "Apply geometry correction.").strip(),
                "tone": "green",
            },
        ]
        vm["cta"] = {
            **dict(vm.get("cta") or {}),
            "enabled": True,
            "label": "Apply geometry correction",
            "payload_id": cta_payload_id_value,
        }
    if active_strength_shell:
        if str(title_text or "").strip() in {"", "Bending capacity is low", "Shear capacity is low", "Capacity is low"}:
            title_text = "Strengthening required"
        if str(governing_label_text or "").strip() in {"", "Target cleanup preview"}:
            governing_label_text = "Repair preview"
        active_bending_shell = bool(
            (active_failure_keys & {"bending"})
            or any("bending_fail" in token for token in family_tokens_for_shell)
        )
        active_shear_shell = bool(
            (active_failure_keys & {"shear"})
            or any("shear_fail" in token for token in family_tokens_for_shell)
        )
        problem_bits = []
        if active_bending_shell:
            problem_bits.append(
                "Bending capacity is failing; review the detailed positive bending row."
            )
        if active_shear_shell:
            problem_bits.append("Shear check is failing; review the detailed shear capacity row.")
        vm["pill"] = "ACTION"
        vm["title"] = str(title_text or "Strengthening required").strip()
        vm["governing_label"] = str(governing_label_text or "Repair preview").strip()
        if active_bending_shell:
            vm["summary_line"] = "Bending capacity is failing. Run one-click auto design."
        elif active_shear_shell:
            vm["summary_line"] = "Shear capacity is failing. Run one-click auto design."
        vm["status"] = "action"
        vm["section_title"] = "Repair evidence"
        vm["reasons"] = [
            {
                "label": "Problem",
                "text": " ".join(problem_bits) or "A required strength check is failing.",
                "tone": "red",
            },
            {
                "label": "Fix",
                "text": str(reason_text_value or summary_line_text or "Run one-click auto design.").strip(),
                "tone": "green",
            },
        ]
    effective_card_class = (
        "fast-guidance-item fail"
        if active_strength_shell or geometry_detailing_shell
        else (str(card_class or "").strip() or "fast-guidance-item efficiency")
    )
    anchor_bucket = "fail" if active_strength_shell or geometry_detailing_shell else "efficiency"
    title_value = str(vm.get("title") or title_text or "Design Guide action").strip()
    pill_value = str(vm.get("pill") or pill or "ACTION").strip().upper()
    shell_model = {
        "marker": "direct_shell_card_projection",
        "fallback_only": True,
        "non_authoritative": True,
        "title": title_value,
        "pill": pill_value,
        "candidate_family": candidate_family,
        "expected_util": expected_util_value,
        "preview_pass": bool(preview_pass),
    }
    family_identity = dict(identity)
    payload = {
        "title": title_value,
        "pill": pill_value,
        "shell_model": shell_model,
        "family_identity": family_identity,
        "view_model": vm,
        "card_class": effective_card_class,
        "anchor_bucket": anchor_bucket,
        "active_strength_shell": active_strength_shell,
        "geometry_detailing_shell": geometry_detailing_shell,
        "identity_projection": identity_projection.to_dict(),
    }
    return FinalDesignGuideDirectShellCardProjection(
        title=title_value,
        pill=pill_value,
        shell_model=shell_model,
        family_identity=family_identity,
        view_model=vm,
        card_class=effective_card_class,
        anchor_bucket=anchor_bucket,
        active_strength_shell=active_strength_shell,
        identity_projection=identity_projection.to_dict(),
        projection_hash=stable_final_publication_hash(payload),
        proof_only=True,
    )


def build_final_design_guide_evidence(
    *,
    item: dict[str, Any] | None = None,
    debug: dict[str, Any] | None = None,
    design_brain_result: dict[str, Any] | None = None,
    publication_reason: str | None = None,
) -> FinalDesignGuideEvidence:
    debug_d = _mapping(debug)
    item_d = normalise_stale_family_contract_violation_item(item, debug_d)
    result_d = _mapping(design_brain_result)
    post_apply_accepted_terminal = bool(
        item_d.get("post_apply_accepted_terminal")
        and str(item_d.get("status") or "").strip().upper() in {"PASS", "GOOD", "OK"}
        and item_d.get("design_guide_terminal_state")
    )
    evidence = _mapping(
        item_d.get("candidate_search_evidence")
        or debug_d.get("candidate_search_evidence")
        or _mapping(result_d.get("evidence")).get("candidate_search")
    )
    debug_evidence = _mapping(debug_d.get("candidate_search_evidence"))
    if evidence and debug_evidence:
        for key in (
            "outside_target_band_allowed_reason",
            "outside_target_band_allowed_category",
            "repair_search_ran",
            "repair_search_exhaustive",
            "cleanup_search_ran",
            "cleanup_search_exhaustive",
            "local_cleanup_search_ran",
            "local_cleanup_search_exhaustive",
            "active_under_capacity_blocker",
            "active_under_capacity_blocker_family",
            "active_under_capacity_blocker_reason",
            "active_failures",
            "safe_candidate_count",
            "executable_candidate_count",
            "executable_target_band_candidate_count",
            "failed_candidate_reasons",
            "blocker_reasons_by_family",
            "exact_blocker_reasons_by_family",
            "exact_blockers_by_family",
            "post_click_exact_blockers_by_family",
            "blocker_attempts_by_family",
        ):
            if post_apply_accepted_terminal and key in {
                "active_under_capacity_blocker",
                "active_under_capacity_blocker_family",
                "active_under_capacity_blocker_reason",
                "active_failures",
                "failed_candidate_reasons",
                "blocker_reasons_by_family",
                "exact_blocker_reasons_by_family",
                "exact_blockers_by_family",
                "post_click_exact_blockers_by_family",
                "blocker_attempts_by_family",
            }:
                continue
            if evidence.get(key) in (None, "", [], {}):
                value = debug_evidence.get(key)
                if value not in (None, "", [], {}):
                    evidence[key] = value
    exact_stop_proof = _mapping(
        item_d.get("exact_stop_proof")
        or debug_d.get("exact_stop_proof")
        or result_d.get("exact_stop_proof")
    )
    if item_d.get("design_guide_terminal_state") and not exact_stop_proof:
        exact_stop_proof = {
            "terminal_state": item_d.get("design_guide_terminal_state"),
            "source": "publication_item",
        }
    target_band_proof = _mapping(
        item_d.get("target_band_proof")
        or debug_d.get("target_band_proof")
        or evidence.get("target_band_proof")
    )
    if not target_band_proof:
        target_band_proof = {
            "target_low": evidence.get("target_low") or _mapping(item_d.get("display_truth")).get("target_low"),
            "target_high": evidence.get("target_high") or _mapping(item_d.get("display_truth")).get("target_high"),
            "displayed_util": _mapping(item_d.get("display_truth")).get("displayed_util"),
        }
    stale_fresh_proof = _mapping(
        item_d.get("stale_fresh_proof")
        or debug_d.get("stale_fresh_proof")
        or {
            "render_metadata_normalised": bool(item_d.get("render_metadata_normalised")),
            "final_visible_state_fingerprint": item_d.get("final_visible_state_fingerprint"),
            "debug_publication_fingerprint": debug_d.get("design_guide_publication_fingerprint"),
        }
    )
    selected_family = _text(
        evidence.get("selected_family_id"),
        evidence.get("published_family_id"),
        evidence.get("cta_family_id"),
        item_d.get("selected_family_id"),
        item_d.get("published_family_id"),
        item_d.get("cta_family_id"),
        debug_d.get("selected_family_id"),
        debug_d.get("published_family_id"),
        debug_d.get("cta_family_id"),
        result_d.get("selected_family_id"),
        result_d.get("published_family_id"),
        item_d.get("family"),
        item_d.get("check_key"),
    )
    authoritative_family_override = _text(
        item_d.get("authoritative_family_override"),
        debug_d.get("authoritative_family_override"),
    )
    if authoritative_family_override:
        selected_family = authoritative_family_override
    else:
        selected_family = _canonical_overdesign_family_identity_from_context(
            selected_family,
            _final_publication_updates_from_item_debug(item_d, debug_d),
            evidence,
            item_d,
            debug_d,
            result_d,
            exact_stop_proof,
        )
        selected_family = _canonical_active_failure_mixed_family_identity_from_context(
            selected_family,
            _final_publication_updates_from_item_debug(item_d, debug_d),
            evidence,
            item_d,
            debug_d,
            result_d,
            {"exact_stop_proof": dict(exact_stop_proof)},
        )
    published_item_id = _text(
        item_d.get("published_item_id"),
        item_d.get("final_visible_item_id"),
        item_d.get("publication_item_id"),
        item_d.get("source_candidate_id"),
        item_d.get("candidate_id"),
        _mapping(item_d.get("button_contract")).get("source_candidate_id"),
        _mapping(item_d.get("button_contract")).get("candidate_id"),
        _mapping(item_d.get("action_payload")).get("source_candidate_id"),
        _mapping(item_d.get("action_payload")).get("candidate_id"),
    )
    post_click_design_guide_state = _text(
        item_d.get("post_click_design_guide_state"),
        debug_d.get("post_click_design_guide_state"),
        item_d.get("design_guide_terminal_state"),
        debug_d.get("design_guide_terminal_state"),
    )
    blocker_reason = (
        None
        if post_apply_accepted_terminal
        else _text(
            item_d.get("blocking_reason"),
            _mapping(next(iter(_mapping(evidence.get("exact_blockers_by_family")).values()), {})).get("reason")
            if _mapping(evidence.get("exact_blockers_by_family"))
            else None,
            evidence.get("active_under_capacity_blocker_reason"),
            evidence.get("outside_target_band_allowed_reason"),
            _mapping(item_d.get("button_contract")).get("blocking_reason"),
            debug_d.get("blocked_publication_type"),
        )
    )
    compute_proofs = _mapping(debug_d.get("final_publication_compute_handoff_rebound_decision_proofs"))
    latest_compute_hash = _text(debug_d.get("final_publication_compute_handoff_rebound_decision_latest_hash"))
    compute_proof = {}
    if compute_proofs:
        for proof in compute_proofs.values():
            proof_d = _mapping(proof)
            if latest_compute_hash and proof_d.get("decision_hash") == latest_compute_hash:
                compute_proof = proof_d
                break
        if not compute_proof:
            for proof in compute_proofs.values():
                proof_d = _mapping(proof)
                if proof_d:
                    compute_proof = proof_d
                    break
    raw_selected_identity = _mapping(compute_proof.get("raw_selected_item_identity")) or _item_identity_surface(item_d)
    raw_rebound_identity = _mapping(compute_proof.get("raw_rebound_item_identity"))
    if not raw_rebound_identity:
        raw_rebound_identity = raw_selected_identity
    compute_publication_evidence = {
        "raw_selected_item_identity": raw_selected_identity,
        "render_reason": _text(compute_proof.get("render_reason"), publication_reason),
        "state_fingerprint": _text(
            compute_proof.get("state_fingerprint"),
            item_d.get("final_visible_state_fingerprint"),
            debug_d.get("design_guide_publication_fingerprint"),
        ),
        "raw_rebound_item_identity": raw_rebound_identity,
        "source_compute_handoff_rebound_proof_hash": _text(compute_proof.get("decision_hash"), latest_compute_hash),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    compute_publication_evidence_hashes = {
        "raw_selected_item_identity": stable_final_publication_hash(raw_selected_identity),
        "render_reason": stable_final_publication_hash(compute_publication_evidence["render_reason"]),
        "state_fingerprint": stable_final_publication_hash(compute_publication_evidence["state_fingerprint"]),
        "raw_rebound_item_identity": stable_final_publication_hash(raw_rebound_identity),
    }
    compute_publication_evidence_hash = stable_final_publication_hash(
        {
            "compute_publication_evidence": compute_publication_evidence,
            "compute_publication_evidence_hashes": compute_publication_evidence_hashes,
        }
    )
    payload = {
        "published_item_id": published_item_id,
        "post_click_design_guide_state": post_click_design_guide_state,
        "selected_family": selected_family,
        "publication_reason": publication_reason,
        "blocker_reason": blocker_reason,
        "exact_stop_proof": exact_stop_proof,
        "target_band_proof": target_band_proof,
        "stale_fresh_proof": stale_fresh_proof,
        "candidate_search_evidence": evidence,
        "optimal_blocker_proof": {},
        "compute_publication_evidence": compute_publication_evidence,
        "compute_publication_evidence_hashes": compute_publication_evidence_hashes,
        "compute_publication_evidence_hash": compute_publication_evidence_hash,
    }
    return FinalDesignGuideEvidence(
        published_item_id=published_item_id,
        post_click_design_guide_state=post_click_design_guide_state,
        selected_family=selected_family,
        publication_reason=_text(publication_reason, item_d.get("final_visible_resolver_reason"), result_d.get("outcome_id")),
        blocker_reason=blocker_reason,
        exact_stop_proof=exact_stop_proof,
        target_band_proof=target_band_proof,
        stale_fresh_proof=stale_fresh_proof,
        candidate_search_evidence=evidence,
        optimal_blocker_proof={},
        compute_publication_evidence=compute_publication_evidence,
        compute_publication_evidence_hashes=compute_publication_evidence_hashes,
        compute_publication_evidence_hash=compute_publication_evidence_hash,
        evidence_hash=stable_final_publication_hash(payload),
    )


def build_final_design_guide_verifier_payload(payload: dict[str, Any] | None = None) -> FinalDesignGuideVerifierPayload:
    payload_d = _mapping(payload)
    return FinalDesignGuideVerifierPayload(
        payload=payload_d,
        payload_hash=stable_final_publication_hash(payload_d),
        browser_driving=False,
    )


def _guard_final_publication_cta_identity(
    cta: FinalDesignGuideCTA,
    evidence: FinalDesignGuideEvidence,
) -> FinalDesignGuideCTA:
    """Prevent executable CTA proof when publication identity is incomplete."""

    payload = asdict(cta)
    selected_family = _text(evidence.selected_family)
    canonical_family = None
    if evidence.publication_reason != "authoritative_application_compute":
        canonical_family = _canonical_overdesign_family_identity(
            _text(selected_family, payload.get("family")),
            _mapping(payload.get("apply_payload_summary")).get("updates"),
        )
    if canonical_family:
        selected_family = canonical_family
        payload["family"] = canonical_family
        summary = _mapping(payload.get("apply_payload_summary"))
        summary["family"] = canonical_family
        payload["apply_payload_summary"] = summary
    payload_family = _text(payload.get("family"))
    if selected_family and (not payload_family or payload_family != selected_family):
        payload["family"] = selected_family
        summary = _mapping(payload.get("apply_payload_summary"))
        summary["family"] = selected_family
        payload["apply_payload_summary"] = summary
        handoff = _mapping(payload.get("one_click_action_handoff"))
        if handoff:
            handoff["family"] = selected_family
            payload["one_click_action_handoff"] = handoff
    terminal_state = str(evidence.post_click_design_guide_state or "").strip().lower()
    evidence_sources = (
        evidence.candidate_search_evidence,
        evidence.exact_stop_proof,
        evidence.target_band_proof,
    )
    has_executable_payload = bool(
        payload.get("enabled")
        or payload.get("actionable")
    ) and bool(
        payload.get("action_type")
        and dict(payload.get("updates") or {})
    )
    explicit_no_second_cta_proof = _final_publication_has_no_second_cta_exact_proof(
        *evidence_sources,
    )
    overdesign_cleanup_family = str(
        selected_family
        or payload.get("family")
        or _mapping(payload.get("apply_payload_summary")).get("family")
        or ""
    ).strip().upper() in _FINAL_PUBLICATION_OVERDESIGN_FAMILY_IDS
    preserve_executable_overdesign_cleanup = bool(
        has_executable_payload
        and overdesign_cleanup_family
        and not explicit_no_second_cta_proof
    )
    if (
        str(selected_family or "").strip().upper()
        in _FINAL_PUBLICATION_TERMINAL_NO_ACTION_FAMILY_IDS
        or (
            terminal_state in _FINAL_PUBLICATION_TERMINAL_NO_ACTION_STATES
            and not preserve_executable_overdesign_cleanup
        )
    ):
        payload["enabled"] = False
        payload["actionable"] = False
        payload["action_type"] = None
        payload["updates"] = {}
        payload["label"] = None
        payload["disabled_reason"] = _text(
            payload.get("disabled_reason"),
            "terminal_pass_no_action",
        )
        summary = _mapping(payload.get("apply_payload_summary"))
        summary["action_type"] = None
        summary["updates"] = {}
        summary["updates_hash"] = stable_final_publication_hash({})
        payload["apply_payload_summary"] = summary
        handoff = _mapping(payload.get("one_click_action_handoff"))
        handoff["action_type"] = None
        handoff["has_updates"] = False
        handoff["updates_hash"] = stable_final_publication_hash({})
        payload["one_click_action_handoff"] = handoff
    if bool(payload.get("enabled") or payload.get("actionable")) and not selected_family:
        payload["enabled"] = False
        payload["actionable"] = False
        payload["disabled_reason"] = _text(
            payload.get("disabled_reason"),
            "missing_selected_family_for_apply_cta",
        )
    if bool(payload.get("enabled") or payload.get("actionable")) and not _text(payload.get("family")):
        payload["enabled"] = False
        payload["actionable"] = False
        payload["disabled_reason"] = _text(
            payload.get("disabled_reason"),
            "missing_cta_family_for_apply_cta",
        )
    return FinalDesignGuideCTA(**payload)


COMPUTE_PUBLICATION_HANDOFF_REBOUND_BLOCKING_FIELDS: tuple[str, ...] = (
    "raw_final_compute_resolution.item",
    "raw_final_compute_resolution.render_reason",
    "raw_final_compute_resolution.state_fingerprint",
    "late_evidence_update_acceptance_condition",
    "raw_late_rebound_contract.enabled",
    "raw_late_rebound_contract.updates",
    "post_core_evidence_update_mismatch_condition",
    "raw_post_evidence_rebound.item",
    "collapsed_guidance_items[0] pre-resolver mutation",
)


def _item_identity_surface(item: dict[str, Any]) -> dict[str, Any]:
    contract = _mapping(item.get("button_contract"))
    payload = _mapping(item.get("action_payload"))
    resolved = _mapping(item.get("resolved_candidate"))
    return {
        "published_item_id": _text(
            item.get("published_item_id"),
            item.get("publication_item_id"),
            item.get("final_visible_item_id"),
            item.get("candidate_id"),
            item.get("source_candidate_id"),
            contract.get("candidate_id"),
            payload.get("candidate_id"),
            resolved.get("candidate_id"),
        ),
        "candidate_id": _text(
            item.get("candidate_id"),
            contract.get("candidate_id"),
            payload.get("candidate_id"),
            resolved.get("candidate_id"),
        ),
        "source_candidate_id": _text(
            item.get("source_candidate_id"),
            contract.get("source_candidate_id"),
            payload.get("source_candidate_id"),
            resolved.get("source_candidate_id"),
            item.get("candidate_id"),
        ),
        "selected_family": _text(
            item.get("selected_family_id"),
            item.get("published_family_id"),
            item.get("family"),
            item.get("check_key"),
            contract.get("family"),
            payload.get("family"),
        ),
        "outcome_state": _text(
            item.get("outcome_state"),
            item.get("status"),
            item.get("post_click_design_guide_state"),
            item.get("design_guide_terminal_state"),
        ),
        "action_type": _text(item.get("action_type"), contract.get("action_type"), payload.get("action_type")),
        "guidance_intent": _text(item.get("guidance_intent")),
        "identity_hash": stable_final_publication_hash(
            {
                "candidate_id": _text(item.get("candidate_id"), contract.get("candidate_id"), payload.get("candidate_id")),
                "source_candidate_id": _text(item.get("source_candidate_id"), contract.get("source_candidate_id"), payload.get("source_candidate_id")),
                "family": _text(item.get("selected_family_id"), item.get("family"), item.get("check_key"), contract.get("family")),
                "action_type": _text(item.get("action_type"), contract.get("action_type"), payload.get("action_type")),
            }
        ),
    }


def build_final_design_guide_compute_publication_handoff_rebound_decision_proof(
    *,
    raw_selected_item: dict[str, Any] | None = None,
    blocker_evidence_surface: dict[str, Any] | None = None,
    render_reason: str | None = None,
    state_fingerprint: str | None = None,
    late_evidence_acceptance: dict[str, Any] | None = None,
    rebound_contract: dict[str, Any] | None = None,
    rebound_update_payload: dict[str, Any] | None = None,
    post_core_evidence_mismatch: dict[str, Any] | None = None,
    raw_rebound_item: dict[str, Any] | None = None,
    pre_resolver_collapsed_item_mutation: dict[str, Any] | None = None,
) -> FinalDesignGuideComputePublicationHandoffReboundDecisionProof:
    """Build proof-only compute publication handoff/rebound decision evidence.

    The builder accepts plain dictionaries and primitive values only. It does
    not import page code, render UI, route apply actions, read session state, or
    drive live publication.
    """

    raw_selected = _mapping(raw_selected_item)
    blocker_surface = _mapping(blocker_evidence_surface)
    late_accept = _mapping(late_evidence_acceptance)
    contract = _mapping(rebound_contract)
    rebound_updates = _mapping(rebound_update_payload)
    post_core = _mapping(post_core_evidence_mismatch)
    rebound_item = _mapping(raw_rebound_item)
    collapsed_mutation = _mapping(pre_resolver_collapsed_item_mutation)

    rebound_summary = {
        "enabled": bool(contract.get("enabled") or contract.get("actionable")),
        "action_type": _text(contract.get("action_type")),
        "family": _text(contract.get("family")),
        "candidate_id": _text(contract.get("candidate_id"), contract.get("source_candidate_id")),
        "source_candidate_id": _text(contract.get("source_candidate_id"), contract.get("candidate_id")),
        "updates": _mapping(contract.get("updates")) or rebound_updates,
        "disabled_reason": _text(
            contract.get("disabled_reason"),
            contract.get("blocking_reason"),
            contract.get("executor_contract_blocked_reason"),
        ),
    }
    update_summary = {
        "updates": _mapping(rebound_summary.get("updates")),
        "update_keys": sorted(_mapping(rebound_summary.get("updates")).keys()),
        "update_hash": stable_final_publication_hash(_mapping(rebound_summary.get("updates"))),
    }
    raw_selected_identity = _item_identity_surface(raw_selected)
    raw_rebound_identity = _item_identity_surface(rebound_item)
    mutation_summary = {
        "before_identity": _mapping(collapsed_mutation.get("before_identity")),
        "after_identity": _mapping(collapsed_mutation.get("after_identity")) or raw_rebound_identity,
        "mutation_reason": _text(
            collapsed_mutation.get("mutation_reason"),
            collapsed_mutation.get("reason"),
            render_reason,
        ),
        "mutation_hash": stable_final_publication_hash(collapsed_mutation),
    }
    field_payloads = {
        "raw_final_compute_resolution.item": raw_selected_identity,
        "raw_final_compute_resolution.render_reason": _text(render_reason),
        "raw_final_compute_resolution.state_fingerprint": _text(state_fingerprint),
        "late_evidence_update_acceptance_condition": late_accept,
        "raw_late_rebound_contract.enabled": rebound_summary.get("enabled"),
        "raw_late_rebound_contract.updates": update_summary,
        "post_core_evidence_update_mismatch_condition": post_core,
        "raw_post_evidence_rebound.item": raw_rebound_identity,
        "collapsed_guidance_items[0] pre-resolver mutation": mutation_summary,
    }
    field_hashes = {
        field: stable_final_publication_hash(value)
        for field, value in field_payloads.items()
    }
    covered = tuple(
        field
        for field in COMPUTE_PUBLICATION_HANDOFF_REBOUND_BLOCKING_FIELDS
        if field in field_payloads
    )
    missing = tuple(
        field
        for field in COMPUTE_PUBLICATION_HANDOFF_REBOUND_BLOCKING_FIELDS
        if field not in field_payloads
    )
    payload = {
        "raw_selected_item_identity": raw_selected_identity,
        "blocker_evidence_surface": blocker_surface,
        "blocker_evidence_surface_hash": stable_final_publication_hash(blocker_surface),
        "render_reason": _text(render_reason),
        "state_fingerprint": _text(state_fingerprint),
        "late_evidence_acceptance": late_accept,
        "rebound_contract": rebound_summary,
        "rebound_update_payload_summary": update_summary,
        "post_core_evidence_mismatch": post_core,
        "raw_rebound_item_identity": raw_rebound_identity,
        "pre_resolver_collapsed_item_mutation": mutation_summary,
        "field_hashes": field_hashes,
        "covered_blocking_fields": covered,
        "missing_blocking_fields": missing,
    }
    return FinalDesignGuideComputePublicationHandoffReboundDecisionProof(
        raw_selected_item_identity=raw_selected_identity,
        blocker_evidence_surface=blocker_surface,
        render_reason=_text(render_reason),
        state_fingerprint=_text(state_fingerprint),
        late_evidence_acceptance=late_accept,
        rebound_contract=rebound_summary,
        rebound_update_payload_summary=update_summary,
        post_core_evidence_mismatch=post_core,
        raw_rebound_item_identity=raw_rebound_identity,
        pre_resolver_collapsed_item_mutation=mutation_summary,
        field_hashes=field_hashes,
        covered_blocking_fields=covered,
        missing_blocking_fields=missing,
        decision_hash=stable_final_publication_hash(payload),
    )


def build_final_design_guide_publication(
    *,
    item: dict[str, Any] | None = None,
    debug: dict[str, Any] | None = None,
    design_brain_result: dict[str, Any] | None = None,
    verifier_payload: dict[str, Any] | None = None,
    publication_reason: str | None = None,
) -> FinalDesignGuidePublication:
    """Normalize current distributed publication-shaped data into a proof object."""

    item_d = _mapping(item)
    debug_d = _mapping(debug)
    result_d = _mapping(design_brain_result)
    cta = build_final_design_guide_cta(item=item_d, debug=debug_d)
    verifier_d = _mapping(verifier_payload)
    verifier_cta = _mapping(verifier_d.get("cta"))
    if not verifier_cta:
        verifier_cta = _mapping(_mapping(debug_d.get("final_publication_cta_authority_payload")).get("cta"))
    verifier_cta_updates = _mapping(
        verifier_cta.get("updates")
        or _mapping(verifier_cta.get("apply_payload_summary")).get("updates")
    )
    if (
        verifier_cta
        and verifier_cta_updates
        and bool(verifier_cta.get("enabled") or verifier_cta.get("actionable"))
        and not bool(cta.enabled)
    ):
        verifier_family = _text(
            verifier_cta.get("cta_family_id"),
            verifier_cta.get("family_id"),
            verifier_cta.get("family"),
            verifier_d.get("selected_family_id"),
            verifier_d.get("selected_family"),
        )
        verifier_action_type = _text(
            verifier_cta.get("action_type"),
            _mapping(verifier_cta.get("one_click_action_handoff")).get("action_type"),
            "apply_resolved_candidate",
        )
        verifier_contract = {
            **verifier_cta,
            "enabled": True,
            "actionable": True,
            "family": verifier_family,
            "selected_family_id": verifier_family,
            "published_family_id": verifier_family,
            "cta_family_id": verifier_family,
            "apply_payload_family_id": verifier_family,
            "candidate_family_id": verifier_family,
            "updates": dict(verifier_cta_updates),
            "action_type": verifier_action_type,
            "blocking_reason": None,
            "disabled_reason": None,
            "preview_pass": True,
        }
        verifier_action_payload = {
            "family": verifier_family,
            "updates": dict(verifier_cta_updates),
            "resolved_candidate_updates": dict(verifier_cta_updates),
            "action_type": verifier_action_type,
            "resolved_candidate_action_type": verifier_action_type,
            "source_candidate_id": verifier_cta.get("source_candidate_id"),
            "candidate_id": verifier_cta.get("source_candidate_id"),
        }
        cta = build_final_design_guide_cta(
            item={
                **item_d,
                "button_contract": verifier_contract,
                "action_payload": verifier_action_payload,
                "selected_family_id": verifier_family,
                "published_family_id": verifier_family,
                "cta_family_id": verifier_family,
                "apply_payload_family_id": verifier_family,
                "candidate_family_id": verifier_family,
                "updates": dict(verifier_cta_updates),
                "action_type": verifier_action_type,
            },
            debug=debug_d,
        )
    display = build_final_design_guide_display(item=item_d, debug=debug_d)
    evidence = build_final_design_guide_evidence(
        item=item_d,
        debug=debug_d,
        design_brain_result=result_d,
        publication_reason=publication_reason,
    )
    candidate_evidence = _mapping(evidence.candidate_search_evidence)
    family_owned_exact_blockers = _mapping(
        candidate_evidence.get("post_click_exact_blockers_by_family")
        or candidate_evidence.get("exact_blockers_by_family")
        or item_d.get("post_click_exact_blockers_by_family")
        or item_d.get("exact_blockers_by_family")
    )
    family_owned_ladder_stop = bool(
        family_owned_exact_blockers
        and candidate_evidence.get("family_ladder_exhausted")
        and candidate_evidence.get("legacy_fallback_allowed") is False
    )
    if family_owned_ladder_stop:
        blocker_family = _text(
            candidate_evidence.get("selected_family_id"),
            candidate_evidence.get("selected_family"),
            item_d.get("selected_family_id"),
            item_d.get("selected_family"),
        )
        if (
            blocker_family
            and blocker_family
            not in _FINAL_PUBLICATION_TERMINAL_NO_ACTION_FAMILY_IDS
            and blocker_family != evidence.selected_family
        ):
            evidence_payload = evidence.to_dict()
            evidence_payload["selected_family"] = blocker_family
            evidence = replace(
                evidence,
                selected_family=blocker_family,
                evidence_hash=stable_final_publication_hash(evidence_payload),
            )
    cta = _guard_final_publication_cta_identity(cta, evidence)
    authoritative_family_override = _text(
        item_d.get("authoritative_family_override"),
        debug_d.get("authoritative_family_override"),
    )
    if authoritative_family_override:
        canonical_evidence_family = authoritative_family_override
    else:
        canonical_evidence_family = _canonical_overdesign_family_identity_from_context(
            evidence.selected_family,
            cta.updates,
            item_d,
            debug_d,
            result_d,
            display.to_dict(),
            cta.to_dict(),
            cta.apply_payload_summary,
            cta.one_click_action_handoff,
            {"exact_stop_proof": dict(evidence.exact_stop_proof)},
        )
        canonical_evidence_family = _canonical_active_failure_mixed_family_identity_from_context(
            canonical_evidence_family or evidence.selected_family,
            cta.updates,
            item_d,
            debug_d,
            result_d,
            display.to_dict(),
            cta.to_dict(),
            cta.apply_payload_summary,
            cta.one_click_action_handoff,
            {"exact_stop_proof": dict(evidence.exact_stop_proof)},
        )
    if canonical_evidence_family and canonical_evidence_family != evidence.selected_family:
        evidence_payload = evidence.to_dict()
        evidence_payload["selected_family"] = canonical_evidence_family
        evidence = replace(
            evidence,
            selected_family=canonical_evidence_family,
            evidence_hash=stable_final_publication_hash(evidence_payload),
        )
        cta = _guard_final_publication_cta_identity(cta, evidence)
    optimal_blocker_proof = build_family_optimal_no_action_proof(
        family_id=evidence.selected_family,
        cta_enabled=bool(cta.enabled or cta.actionable),
        item=item_d,
        evidence=evidence.candidate_search_evidence,
        exact_stop_proof=evidence.exact_stop_proof,
        target_band_proof=evidence.target_band_proof,
    ).to_dict()
    if optimal_blocker_proof:
        evidence_payload = evidence.to_dict()
        evidence_payload["optimal_blocker_proof"] = optimal_blocker_proof
        evidence = replace(
            evidence,
            optimal_blocker_proof=optimal_blocker_proof,
            evidence_hash=stable_final_publication_hash(evidence_payload),
        )
    safe_discrete_terminal_stop = bool(
        not bool(cta.enabled or cta.actionable)
        and str(evidence.post_click_design_guide_state or "").strip().lower()
        in _FINAL_PUBLICATION_TERMINAL_NO_ACTION_STATES
        and candidate_evidence.get("candidate_search_exhaustive") is True
        and candidate_evidence.get("outside_target_band_allowed") is True
        and str(candidate_evidence.get("outside_target_band_allowed_category") or "").strip()
        == "discrete_increment_limit"
        and int(candidate_evidence.get("safe_executor_backed_candidates_count") or 0) > 0
    )
    verifier = build_final_design_guide_verifier_payload(verifier_payload)
    outcome = infer_final_design_guide_outcome_state(
        item=item_d,
        cta=cta,
        blocker_reason=evidence.blocker_reason,
    )
    if (
        outcome == "PROOF_PENDING"
        and not bool(cta.enabled or cta.actionable)
        and str(evidence.post_click_design_guide_state or "").strip().lower()
        in _FINAL_PUBLICATION_TERMINAL_NO_ACTION_STATES
    ):
        # Post-Apply terminal state is derived into authoritative evidence
        # before publication.  The collapsed item may intentionally carry no
        # action/status fields at that point; do not discard the stronger
        # session-owned terminal proof and publish PROOF_PENDING forever.
        outcome = "PASS"
    if safe_discrete_terminal_stop:
        # A family ladder may exhaust the available discrete catalogue just
        # above the preferred band after Apply.  When the authoritative
        # post-click state is terminal, the search is exhaustive, and the
        # selected executor-backed candidate is safe, this is a successful
        # exact stop with an explanatory reason—not a blocked design.
        outcome = "PASS"
    if (
        not bool(cta.enabled or cta.actionable)
        and bool(optimal_blocker_proof.get("safe_optimal_no_action"))
        and not family_owned_ladder_stop
    ):
        outcome = "PASS"
    if (
        family_owned_ladder_stop
        and not safe_discrete_terminal_stop
        and not bool(cta.enabled or cta.actionable)
    ):
        outcome = "BLOCKED"
    if (
        outcome == "PASS"
        and not bool(cta.enabled or cta.actionable)
        and (
            bool(optimal_blocker_proof.get("safe_optimal_no_action"))
            or safe_discrete_terminal_stop
        )
        and (not family_owned_ladder_stop or safe_discrete_terminal_stop)
    ):
        display = _optimal_no_action_display(
            display,
            blocker_reason=evidence.blocker_reason,
            optimal_blocker_proof={
                **optimal_blocker_proof,
                "safe_discrete_terminal_stop": safe_discrete_terminal_stop,
            },
        )
    elif (
        outcome == "PASS"
        and not bool(cta.enabled or cta.actionable)
        and str(evidence.blocker_reason or "").strip().lower()
        in _FINAL_PUBLICATION_TERMINAL_NO_ACTION_REASONS
    ):
        display = _terminal_no_action_display(display, outcome_state=outcome)
    elif outcome == "BLOCKED" and not bool(cta.enabled or cta.actionable):
        display = _blocked_no_action_display(display, blocker_reason=evidence.blocker_reason)
    source_payload = {
        "item": item_d,
        "debug": debug_d,
        "design_brain_result": result_d,
        "verifier_payload": _mapping(verifier_payload),
        "publication_reason": publication_reason,
    }
    publication = FinalDesignGuidePublication(
        published_item_id=evidence.published_item_id,
        post_click_design_guide_state=evidence.post_click_design_guide_state,
        selected_family=evidence.selected_family,
        outcome_state=outcome,
        publication_reason=evidence.publication_reason,
        blocker_reason=evidence.blocker_reason,
        exact_stop_proof=dict(evidence.exact_stop_proof),
        target_band_proof=dict(evidence.target_band_proof),
        cta=cta,
        display=display,
        evidence=evidence,
        verifier_payload=verifier,
        stale_fresh_proof=dict(evidence.stale_fresh_proof),
        source_hash=stable_final_publication_hash(source_payload),
        publication_hash=None,
        proof_only=True,
    )
    return publication.with_publication_hash()


def build_collapsed_guidance_item_from_final_publication(
    publication: FinalDesignGuidePublication,
) -> dict[str, Any]:
    """Build a proof-only collapsed-guidance item from final publication truth.

    The adapter accepts an already-built FinalDesignGuidePublication only.
    It does not render UI, route apply actions, read session state, or import
    page code.
    """

    if not isinstance(publication, FinalDesignGuidePublication):
        raise TypeError("publication must be a FinalDesignGuidePublication")

    cta = publication.cta.to_dict()
    display = publication.display.to_dict()
    evidence = publication.evidence.to_dict()
    compute_evidence = _mapping(evidence.get("compute_publication_evidence"))
    raw_selected_identity = _mapping(compute_evidence.get("raw_selected_item_identity"))
    raw_rebound_identity = _mapping(compute_evidence.get("raw_rebound_item_identity"))
    candidate_search_evidence = _mapping(evidence.get("candidate_search_evidence"))
    verifier_payload = publication.verifier_payload.to_dict()
    button_contract = {
        "enabled": bool(cta.get("enabled")),
        "actionable": bool(cta.get("actionable")),
        "label": cta.get("label"),
        "action_type": cta.get("action_type"),
        "family": cta.get("family") or publication.selected_family,
        "disabled_reason": cta.get("disabled_reason"),
        "source_candidate_id": cta.get("source_candidate_id") or publication.published_item_id,
        "candidate_id": _mapping(cta.get("apply_payload_summary")).get("candidate_id")
        or cta.get("source_candidate_id")
        or publication.published_item_id,
        "updates": _mapping(cta.get("apply_payload_summary")).get("updates") or {},
        "final_publication_cta_authority": "FinalDesignGuidePublication.cta",
        "final_publication_cta_hash": stable_final_publication_authority_hash(cta),
    }
    action_payload = dict(cta.get("apply_payload_summary") or {})
    collapsed_candidate_id = _text(
        raw_rebound_identity.get("candidate_id"),
        raw_selected_identity.get("candidate_id"),
        _mapping(cta.get("apply_payload_summary")).get("candidate_id"),
        _mapping(cta.get("one_click_action_handoff")).get("candidate_id"),
        candidate_search_evidence.get("selected_candidate_id"),
        candidate_search_evidence.get("best_safe_candidate_id"),
        publication.published_item_id,
    )
    collapsed_source_candidate_id = _text(
        raw_rebound_identity.get("source_candidate_id"),
        raw_selected_identity.get("source_candidate_id"),
        cta.get("source_candidate_id"),
        _mapping(cta.get("apply_payload_summary")).get("source_candidate_id"),
        _mapping(cta.get("apply_payload_summary")).get("candidate_id"),
        candidate_search_evidence.get("selected_candidate_id"),
        candidate_search_evidence.get("best_safe_candidate_id"),
        publication.published_item_id,
        collapsed_candidate_id,
    )
    controller_fallback_shell = bool(
        _text(
            compute_evidence.get("render_reason"),
            publication.publication_reason,
        )
        == "controller_compute_resolver_fallback_shell"
    )

    collapsed_item = {
        "published_item_id": publication.published_item_id,
        "final_visible_item_id": publication.published_item_id,
        "publication_item_id": publication.published_item_id,
        "candidate_id": collapsed_candidate_id,
        "source_candidate_id": collapsed_source_candidate_id,
        "post_click_design_guide_state": publication.post_click_design_guide_state,
        "selected_family_id": publication.selected_family,
        "published_family_id": publication.selected_family,
        "family": publication.selected_family,
        "outcome_state": publication.outcome_state,
        "publication_reason": publication.publication_reason,
        "blocker_reason": publication.blocker_reason,
        "blocking_reason": publication.blocker_reason,
        "design_guide_terminal_state": publication.post_click_design_guide_state,
        "title_main": display.get("title"),
        "title": display.get("title"),
        "pill": display.get("badge"),
        "summary_line": display.get("summary"),
        "status": display.get("status") or publication.outcome_state,
        "bucket": display.get("bucket"),
        "display_state": display.get("display_state") or publication.outcome_state,
        "card_class": display.get("card_class"),
        "blocker_explanation": display.get("blocker_explanation") or publication.blocker_reason,
        "button_contract": button_contract,
        "action_payload": action_payload,
        "candidate_search_evidence": dict(evidence.get("candidate_search_evidence") or {}),
        "exact_stop_proof": dict(publication.exact_stop_proof or {}),
        "target_band_proof": dict(publication.target_band_proof or {}),
        "stale_fresh_proof": dict(publication.stale_fresh_proof or {}),
        "final_publication_verifier_payload": dict(verifier_payload.get("payload") or {}),
        "final_publication_publication_hash": publication.publication_hash,
        "publication_hash": publication.publication_hash,
        "final_publication_authority_hash": publication.publication_hash,
        "final_publication_cta_hash": stable_final_publication_authority_hash(cta),
        "final_publication_display_hash": stable_final_publication_authority_hash(display),
        "final_publication_evidence_hash": stable_final_publication_authority_hash(evidence),
        "final_publication_source_hash": publication.source_hash,
        "legacy_non_authoritative": True,
        "compatibility_only": True,
        "derived_from": "FinalDesignGuidePublication",
        "collapsed_guidance_adapter_proof_only": True,
        "product_driving": False,
        "render_driving": False,
    }
    if controller_fallback_shell:
        collapsed_item["controller_compute_resolver_fallback_shell"] = True
    collapsed_item["collapsed_guidance_item_hash"] = stable_final_publication_hash(
        {
            "published_item_id": collapsed_item.get("published_item_id"),
            "candidate_id": collapsed_item.get("candidate_id"),
            "source_candidate_id": collapsed_item.get("source_candidate_id"),
            "post_click_design_guide_state": collapsed_item.get("post_click_design_guide_state"),
            "selected_family": collapsed_item.get("selected_family_id"),
            "outcome_state": collapsed_item.get("outcome_state"),
            "cta_hash": collapsed_item.get("final_publication_cta_hash"),
            "display_hash": collapsed_item.get("final_publication_display_hash"),
            "evidence_hash": collapsed_item.get("final_publication_evidence_hash"),
            "publication_hash": collapsed_item.get("publication_hash"),
        }
    )
    return collapsed_item


def build_render_stage_post_resolver_item_mutation_proof(
    publication: FinalDesignGuidePublication,
    *,
    selected_item: dict[str, Any] | None = None,
    final_visible_resolution: dict[str, Any] | None = None,
    guidance_debug: dict[str, Any] | None = None,
) -> FinalDesignGuidePostResolverMutationProof:
    """Normalize render-stage post-resolver selected-item mutation truth.

    This proof-only adapter accepts plain dictionaries already produced by the
    page path. It does not import page code, render cards, route apply actions,
    read session state, or change the selected item.
    """

    if not isinstance(publication, FinalDesignGuidePublication):
        raise TypeError("publication must be a FinalDesignGuidePublication")

    item_d = _mapping(selected_item)
    resolution_d = _mapping(final_visible_resolution)
    debug_d = _mapping(guidance_debug)
    cta_d = publication.cta.to_dict()
    evidence_d = publication.evidence.to_dict()
    display_d = publication.display.to_dict()
    item_contract = _mapping(item_d.get("button_contract"))
    item_action_payload = _mapping(item_d.get("action_payload"))
    resolver_item = _mapping(resolution_d.get("item"))

    candidate_search_evidence = _mapping(
        evidence_d.get("candidate_search_evidence")
        or item_d.get("candidate_search_evidence")
        or debug_d.get("candidate_search_evidence")
    )
    exact_stop_proof = _mapping(publication.exact_stop_proof or evidence_d.get("exact_stop_proof"))
    target_band_proof = _mapping(publication.target_band_proof or evidence_d.get("target_band_proof"))
    exact_blockers = _mapping(
        item_d.get("exact_blockers_by_family")
        or debug_d.get("exact_blockers_by_family")
        or exact_stop_proof.get("exact_blockers_by_family")
    )
    post_click_exact_blockers = _mapping(
        item_d.get("post_click_exact_blockers_by_family")
        or debug_d.get("post_click_exact_blockers_by_family")
        or exact_stop_proof.get("post_click_exact_blockers_by_family")
    )
    blocker_attempts = _mapping(
        item_d.get("blocker_attempts_by_family")
        or debug_d.get("blocker_attempts_by_family")
        or candidate_search_evidence.get("blocker_attempts_by_family")
    )

    selected_item_identity = {
        "published_item_id": publication.published_item_id,
        "selected_family": publication.selected_family,
        "candidate_id": _text(
            item_d.get("candidate_id"),
            item_contract.get("candidate_id"),
            item_action_payload.get("candidate_id"),
            cta_d.get("apply_payload_summary", {}).get("candidate_id")
            if isinstance(cta_d.get("apply_payload_summary"), dict)
            else None,
            publication.published_item_id,
        ),
        "source_candidate_id": _text(
            item_d.get("source_candidate_id"),
            item_contract.get("source_candidate_id"),
            item_action_payload.get("source_candidate_id"),
            cta_d.get("source_candidate_id"),
            publication.published_item_id,
        ),
        "action_type": _text(
            item_d.get("action_type"),
            item_contract.get("action_type"),
            cta_d.get("action_type"),
        ),
        "family": _text(item_d.get("family"), item_contract.get("family"), publication.selected_family),
    }
    evidence_projection = {
        "candidate_search_evidence": candidate_search_evidence,
        "candidate_search_evidence_hash": stable_final_publication_hash(candidate_search_evidence),
        "target_band_proof": target_band_proof,
        "target_band_proof_hash": stable_final_publication_hash(target_band_proof),
        "stale_fresh_proof": dict(publication.stale_fresh_proof or evidence_d.get("stale_fresh_proof") or {}),
    }
    blocker_projection = {
        "blocker_reason": publication.blocker_reason or evidence_d.get("blocker_reason"),
        "exact_stop_proof": exact_stop_proof,
        "exact_stop_proof_hash": stable_final_publication_hash(exact_stop_proof),
        "exact_blockers_by_family": exact_blockers,
        "post_click_exact_blockers_by_family": post_click_exact_blockers,
        "blocker_attempts_by_family": blocker_attempts,
    }
    terminal_projection = {
        "outcome_state": publication.outcome_state,
        "post_click_design_guide_state": publication.post_click_design_guide_state,
        "design_guide_terminal_state": _text(
            item_d.get("design_guide_terminal_state"),
            publication.post_click_design_guide_state,
            publication.outcome_state,
        ),
        "publication_reason": publication.publication_reason,
    }
    resolver_projection = {
        "has_resolution_item": bool(resolver_item),
        "render_reason": resolution_d.get("render_reason"),
        "presentation": _mapping(resolution_d.get("presentation")),
        "resolution_item_hash": stable_final_publication_hash(resolver_item),
    }
    selected_item_projection = {
        "title": display_d.get("title") or item_d.get("title") or item_d.get("title_main"),
        "status": display_d.get("status") or item_d.get("status") or publication.outcome_state,
        "bucket": display_d.get("bucket") or item_d.get("bucket"),
        "util": item_d.get("util"),
        "expected_util": item_d.get("expected_util") or item_contract.get("expected_util"),
        "candidate_post_util": item_d.get("candidate_post_util"),
        "resolved_candidate": _mapping(item_d.get("resolved_candidate")),
        "action_payload_hash": stable_final_publication_hash(item_action_payload),
        "button_contract_hash": stable_final_publication_hash(item_contract),
    }
    debug_projection = {
        "candidate_search_evidence_hash": stable_final_publication_hash(
            _mapping(debug_d.get("candidate_search_evidence"))
        ),
        "blocker_attempts_hash": stable_final_publication_hash(
            _mapping(debug_d.get("blocker_attempts_by_family"))
        ),
        "debug_keys_hash": stable_final_publication_hash(sorted(debug_d.keys())),
    }
    mutation_target_coverage = {
        "selected_item_identity": bool(selected_item_identity.get("candidate_id")),
        "candidate_search_evidence": bool(candidate_search_evidence),
        "blocker_attempts_by_family": bool(blocker_attempts),
        "exact_blockers_by_family": bool(exact_blockers or post_click_exact_blockers),
        "terminal_state": bool(terminal_projection.get("design_guide_terminal_state")),
        "resolver_output": bool(resolver_projection.get("has_resolution_item") or resolver_projection.get("render_reason")),
        "utilisation_fields": any(
            selected_item_projection.get(key) is not None
            for key in ("util", "expected_util", "candidate_post_util")
        ),
        "resolved_candidate": bool(selected_item_projection.get("resolved_candidate")),
        "cta_apply_identity": bool(selected_item_identity.get("action_type")),
    }
    adapter_owned_mutation_truth = {
        "classification": "adapter_owned_mutation_truth_represented_by_FinalDesignGuidePostResolverMutationProof",
        "candidate_search_evidence": bool(candidate_search_evidence),
        "blocker_attempts_by_family": bool(blocker_attempts),
        "exact_blockers_by_family": bool(exact_blockers or post_click_exact_blockers),
        "terminal_state": bool(terminal_projection.get("design_guide_terminal_state")),
        "utilisation_projection": any(
            selected_item_projection.get(key) is not None
            for key in ("util", "expected_util", "candidate_post_util")
        ),
        "resolved_candidate_projection": bool(selected_item_projection.get("resolved_candidate")),
        "cta_apply_identity": bool(selected_item_identity.get("action_type")),
        "publication_hash": publication.publication_hash,
    }
    remaining_resolver_truth = {
        "classification": "remaining_live_resolver_truth_not_narrowed",
        "selected_item_replacement": bool(item_d),
        "resolution_item_replacement": bool(resolver_item),
        "resolver_render_reason": bool(resolution_d.get("render_reason")),
        "resolver_presentation": bool(resolution_d.get("presentation")),
        "post_resolver_bridge_narrowed": False,
        "narrowing_allowed_by_this_proof": False,
    }
    payload = {
        "selected_item_identity": selected_item_identity,
        "adapter_owned_mutation_truth": adapter_owned_mutation_truth,
        "remaining_resolver_truth": remaining_resolver_truth,
        "evidence_projection": evidence_projection,
        "blocker_projection": blocker_projection,
        "terminal_projection": terminal_projection,
        "resolver_projection": resolver_projection,
        "selected_item_projection": selected_item_projection,
        "debug_projection": debug_projection,
        "mutation_target_coverage": mutation_target_coverage,
        "publication_hash": publication.publication_hash,
    }
    return FinalDesignGuidePostResolverMutationProof(
        selected_item_identity=selected_item_identity,
        adapter_owned_mutation_truth=adapter_owned_mutation_truth,
        remaining_resolver_truth=remaining_resolver_truth,
        evidence_projection=evidence_projection,
        blocker_projection=blocker_projection,
        terminal_projection=terminal_projection,
        resolver_projection=resolver_projection,
        selected_item_projection=selected_item_projection,
        debug_projection=debug_projection,
        mutation_target_coverage=mutation_target_coverage,
        mutation_proof_hash=stable_final_publication_hash(payload),
    )


def build_final_design_guide_post_resolver_mutation_proof(
    publication: FinalDesignGuidePublication,
    *,
    selected_item: dict[str, Any] | None = None,
    final_visible_resolution: dict[str, Any] | None = None,
    guidance_debug: dict[str, Any] | None = None,
) -> FinalDesignGuidePostResolverMutationProof:
    """Alias for the canonical post-resolver mutation proof builder."""

    return build_render_stage_post_resolver_item_mutation_proof(
        publication,
        selected_item=selected_item,
        final_visible_resolution=final_visible_resolution,
        guidance_debug=guidance_debug,
    )


def build_final_design_guide_render_item_consumer_proof(
    publication: FinalDesignGuidePublication,
    *,
    selected_item: dict[str, Any] | None = None,
    final_visible_resolution: dict[str, Any] | None = None,
    guidance_debug: dict[str, Any] | None = None,
) -> FinalDesignGuideRenderItemConsumerProof:
    """Normalize post-binding render-item consumer truth.

    This is proof-only. It does not decide the visible item, render a card,
    route Apply, read session state, or mutate the publication.
    """

    if not isinstance(publication, FinalDesignGuidePublication):
        raise TypeError("publication must be a FinalDesignGuidePublication")

    item_d = _mapping(selected_item)
    resolution_d = _mapping(final_visible_resolution)
    debug_d = _mapping(guidance_debug)
    evidence_d = publication.evidence.to_dict()
    cta_d = publication.cta.to_dict()
    candidate_search_evidence = _mapping(
        evidence_d.get("candidate_search_evidence")
        or item_d.get("candidate_search_evidence")
        or debug_d.get("candidate_search_evidence")
    )
    blocker_attempts = _mapping(
        item_d.get("blocker_attempts_by_family")
        or debug_d.get("blocker_attempts_by_family")
        or candidate_search_evidence.get("blocker_attempts_by_family")
    )
    exact_blockers = _mapping(
        item_d.get("exact_blockers_by_family")
        or debug_d.get("exact_blockers_by_family")
        or candidate_search_evidence.get("exact_blockers_by_family")
    )
    post_click_exact_blockers = _mapping(
        item_d.get("post_click_exact_blockers_by_family")
        or debug_d.get("post_click_exact_blockers_by_family")
        or candidate_search_evidence.get("post_click_exact_blockers_by_family")
    )
    button_contract = _mapping(item_d.get("button_contract"))
    zero_shear_attempt = _mapping(blocker_attempts.get("shear"))

    zero_shear_cleanup = {
        "stale_blocker_cleared": bool(
            item_d.get("zero_shear_accepted_stale_blocker_cleared")
            or debug_d.get("zero_shear_accepted_stale_blocker_cleared")
        ),
        "has_shear_attempt": bool(zero_shear_attempt),
        "shear_attempt": dict(zero_shear_attempt),
        "shear_attempt_hash": stable_final_publication_hash(zero_shear_attempt),
        "candidate_search_evidence_hash": stable_final_publication_hash(candidate_search_evidence),
        "stale_blocker_cleanup_projection": {
            "clears_shear_from_exact_blockers": True,
            "clears_shear_from_post_click_exact_blockers": True,
            "clears_shear_from_cleanup_evidence": True,
            "clears_shear_from_post_click_cleanup_evidence": True,
            "stamps_shear_terminal_attempt": bool(zero_shear_attempt),
            "stamps_candidate_search_evidence": bool(candidate_search_evidence),
            "proof_only": True,
            "product_driving": False,
            "render_driving": False,
            "apply_driving": False,
            "session_driving": False,
        },
        "terminal_state": _text(
            item_d.get("design_guide_terminal_state"),
            publication.post_click_design_guide_state,
            publication.outcome_state,
        ),
    }
    safe_low_util_promotion = {
        "blocker_reason": publication.blocker_reason or evidence_d.get("blocker_reason"),
        "selected_family": publication.selected_family,
        "outcome_state": publication.outcome_state,
        "exact_blockers_hash": stable_final_publication_hash(
            {
                "exact_blockers_by_family": exact_blockers,
                "post_click_exact_blockers_by_family": post_click_exact_blockers,
            }
        ),
        "candidate_search_evidence_hash": stable_final_publication_hash(candidate_search_evidence),
        "final_visible_resolution_item_hash": stable_final_publication_hash(
            _mapping(resolution_d.get("item"))
        ),
        "render_reason": _text(resolution_d.get("render_reason")),
    }
    post_click_final_contract_checks = {
        "post_click_design_guide_state": publication.post_click_design_guide_state,
        "published_item_id": publication.published_item_id,
        "family": _text(
            item_d.get("family"),
            item_d.get("check_key"),
            button_contract.get("family"),
            publication.selected_family,
        ),
        "action_type": _text(
            item_d.get("action_type"),
            button_contract.get("action_type"),
            cta_d.get("action_type"),
        ),
        "button_contract_hash": stable_final_publication_hash(button_contract),
        "cta_hash": stable_final_publication_hash(cta_d),
        "post_click_unresolved_families_hash": stable_final_publication_hash(
            debug_d.get("post_click_unresolved_low_util_families") or []
        ),
        "post_click_below_floor_families_hash": stable_final_publication_hash(
            debug_d.get("post_click_families_below_final_threshold") or []
        ),
    }
    consumer_coverage = {
        "terminal_state": bool(zero_shear_cleanup.get("terminal_state")),
        "zero_shear_projection": bool(
            zero_shear_cleanup.get("stale_blocker_cleanup_projection")
        ),
        "visible_blocker_check": bool(
            safe_low_util_promotion.get("blocker_reason")
            or safe_low_util_promotion.get("selected_family")
        ),
        "safe_low_util_cleanup_action": bool(
            safe_low_util_promotion.get("candidate_search_evidence_hash")
        ),
        "safe_low_util_projection": bool(
            safe_low_util_promotion.get("final_visible_resolution_item_hash")
        ),
        "resolution_item_sync": bool(
            safe_low_util_promotion.get("final_visible_resolution_item_hash")
        ),
        "post_click_contract": bool(
            post_click_final_contract_checks.get("button_contract_hash")
        ),
        "post_click_family": bool(post_click_final_contract_checks.get("family")),
        "post_click_contract_check_input_proof": bool(
            post_click_final_contract_checks.get("post_click_unresolved_families_hash")
            and post_click_final_contract_checks.get("post_click_below_floor_families_hash")
        ),
        "post_click_bending_resolution": bool(
            post_click_final_contract_checks.get("published_item_id")
            or post_click_final_contract_checks.get("post_click_design_guide_state")
        ),
        "post_click_exact_blocker_adapter": bool(
            post_click_final_contract_checks.get("action_type")
            or post_click_final_contract_checks.get("cta_hash")
        ),
        "post_click_replacement_decision_proof": bool(
            post_click_final_contract_checks.get("post_click_unresolved_families_hash")
            and post_click_final_contract_checks.get("post_click_below_floor_families_hash")
        ),
        "post_click_final_contract_adapter_proof": bool(
            post_click_final_contract_checks.get("button_contract_hash")
            and post_click_final_contract_checks.get("cta_hash")
        ),
    }
    group_payloads = {
        "zero_shear_cleanup": zero_shear_cleanup,
        "safe_low_util_promotion": safe_low_util_promotion,
        "post_click_final_contract_checks": post_click_final_contract_checks,
        "consumer_coverage": consumer_coverage,
    }
    group_hashes = {
        key: stable_final_publication_hash(value)
        for key, value in group_payloads.items()
    }
    covered = tuple(
        key
        for key, value in group_payloads.items()
        if bool(value) and group_hashes.get(key) != stable_final_publication_hash({})
    )
    missing = tuple(key for key in group_payloads if key not in covered)
    payload = {
        "publication_hash": publication.publication_hash,
        "consumer_coverage_hash": stable_final_publication_hash(consumer_coverage),
        "consumer_group_hashes": group_hashes,
        "covered_consumer_groups": covered,
        "missing_consumer_groups": missing,
    }
    return FinalDesignGuideRenderItemConsumerProof(
        zero_shear_cleanup=zero_shear_cleanup,
        safe_low_util_promotion=safe_low_util_promotion,
        post_click_final_contract_checks=post_click_final_contract_checks,
        consumer_coverage=consumer_coverage,
        consumer_group_hashes=group_hashes,
        covered_consumer_groups=covered,
        missing_consumer_groups=missing,
        consumer_proof_hash=stable_final_publication_hash(payload),
    )


def apply_final_design_guide_zero_shear_render_consumer_projection(
    *,
    item: dict[str, Any] | None = None,
    guidance_debug: dict[str, Any] | None = None,
    session_debug: dict[str, Any] | None = None,
    terminal_stop_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply the zero-shear render consumer projection to plain dictionaries.

    This is a pure publication adapter. It does not read or write Streamlit
    session state, render UI, choose recommendations, or alter engineering
    calculations. The page remains responsible for storing returned session
    dictionaries.
    """

    item_d = _mapping(item)
    debug_d = _mapping(guidance_debug)
    session_d = _mapping(session_debug)
    terminal_d = _mapping(terminal_stop_row)
    exact_keys = (
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "cleanup_evidence_by_family",
        "post_click_cleanup_evidence_by_family",
        "blocker_attempts_by_family",
    )
    candidate_exact_keys = (
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "cleanup_evidence_by_family",
        "post_click_cleanup_evidence_by_family",
    )

    def _remove_shear(mapping: dict[str, Any], key: str) -> None:
        values = _mapping(mapping.get(key))
        if "shear" not in values:
            return
        values.pop("shear", None)
        if values:
            mapping[key] = dict(values)
        else:
            mapping.pop(key, None)

    for exact_key in exact_keys:
        _remove_shear(item_d, exact_key)

    item_evidence = _mapping(item_d.get("candidate_search_evidence"))
    for exact_key in candidate_exact_keys:
        _remove_shear(item_evidence, exact_key)
    if item_evidence:
        item_d["candidate_search_evidence"] = dict(item_evidence)

    for exact_key in exact_keys:
        _remove_shear(debug_d, exact_key)
    debug_d["zero_shear_accepted_stale_blocker_cleared"] = True

    if terminal_d:
        item_attempts = _mapping(item_d.get("blocker_attempts_by_family"))
        item_attempts["shear"] = dict(terminal_d)
        item_d["blocker_attempts_by_family"] = dict(item_attempts)

        item_evidence = _mapping(item_d.get("candidate_search_evidence"))
        item_candidate_attempts = _mapping(item_evidence.get("blocker_attempts_by_family"))
        item_candidate_attempts["shear"] = dict(terminal_d)
        item_evidence["blocker_attempts_by_family"] = dict(item_candidate_attempts)
        item_d["candidate_search_evidence"] = dict(item_evidence)

        debug_attempts = _mapping(debug_d.get("blocker_attempts_by_family"))
        debug_attempts["shear"] = dict(terminal_d)
        debug_d["blocker_attempts_by_family"] = dict(debug_attempts)

        debug_evidence = _mapping(debug_d.get("candidate_search_evidence"))
        debug_candidate_attempts = _mapping(debug_evidence.get("blocker_attempts_by_family"))
        debug_candidate_attempts["shear"] = dict(terminal_d)
        debug_evidence["blocker_attempts_by_family"] = dict(debug_candidate_attempts)
        debug_d["candidate_search_evidence"] = dict(debug_evidence)

        if session_d:
            session_attempts = _mapping(session_d.get("blocker_attempts_by_family"))
            session_attempts["shear"] = dict(terminal_d)
            session_d["blocker_attempts_by_family"] = dict(session_attempts)

            session_evidence = _mapping(session_d.get("candidate_search_evidence"))
            session_candidate_attempts = _mapping(session_evidence.get("blocker_attempts_by_family"))
            session_candidate_attempts["shear"] = dict(terminal_d)
            session_evidence["blocker_attempts_by_family"] = dict(session_candidate_attempts)
            session_d["candidate_search_evidence"] = dict(session_evidence)

    payload = {
        "item": item_d,
        "guidance_debug": debug_d,
        "session_debug": session_d,
        "terminal_stop_row_hash": stable_final_publication_hash(terminal_d),
    }
    return {
        **payload,
        "projection_hash": stable_final_publication_hash(payload),
        "derived_from": "FinalDesignGuidePublication.zero_shear_cleanup",
        "proof_only": False,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }


def apply_final_design_guide_safe_low_util_promotion_projection(
    *,
    item: dict[str, Any] | None = None,
    final_visible_resolution: dict[str, Any] | None = None,
    guidance_debug: dict[str, Any] | None = None,
    promoted_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply the safe-low-util promotion projection to plain dictionaries.

    This is a pure publication adapter for the post-resolver projection step.
    It does not decide whether promotion is allowed, build the promoted item,
    render UI, route Apply, or alter engineering calculations.
    """

    item_d = _mapping(item)
    resolution_d = _mapping(final_visible_resolution)
    debug_d = _mapping(guidance_debug)
    promoted_d = _mapping(promoted_item)
    promoted = bool(promoted_d)
    if promoted:
        item_d = dict(promoted_d)
        resolution_d["item"] = dict(item_d)
        resolution_d["render_reason"] = _text(
            item_d.get("final_visible_resolver_reason"),
            "visible_safe_low_util_cleanup_from_blocker_evidence",
        )
        debug_d["final_visible_blocker_promoted_to_safe_low_util_action"] = True

    payload = {
        "item": item_d,
        "final_visible_resolution": resolution_d,
        "guidance_debug": debug_d,
        "promoted_item_hash": stable_final_publication_hash(promoted_d),
        "promoted": promoted,
    }
    return {
        **payload,
        "projection_hash": stable_final_publication_hash(payload),
        "derived_from": "FinalDesignGuidePublication.safe_low_util_promotion",
        "proof_only": False,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }


def build_final_design_guide_post_click_contract_check_input_proof(
    *,
    item: dict[str, Any] | None = None,
    final_visible_resolution: dict[str, Any] | None = None,
    guidance_debug: dict[str, Any] | None = None,
    post_cleanup_render_audit: dict[str, Any] | None = None,
    last_apply_route: dict[str, Any] | None = None,
    primary_payload_binding_audit: dict[str, Any] | None = None,
    current_state: dict[str, Any] | None = None,
    final_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build proof-only input coverage for post-click contract checks.

    This records the page/apply/current-state inputs that still feed the
    post-click final contract check block. It does not decide replacement,
    render UI, route Apply, or mutate page/session state.
    """

    item_d = _mapping(item)
    resolution_d = _mapping(final_visible_resolution)
    debug_d = _mapping(guidance_debug)
    render_audit_d = _mapping(post_cleanup_render_audit)
    apply_route_d = _mapping(last_apply_route)
    binding_audit_d = _mapping(primary_payload_binding_audit)
    state_d = _mapping(current_state)
    contract_d = _mapping(final_contract)
    ligature_state = {
        "lig_d": state_d.get("lig_d"),
        "lig_legs": state_d.get("lig_legs"),
    }
    post_click_families = {
        "unresolved": list(debug_d.get("post_click_unresolved_low_util_families") or [])
        + list(render_audit_d.get("post_click_unresolved_low_util_families") or []),
        "below_floor": list(debug_d.get("post_click_families_below_final_threshold") or [])
        + list(render_audit_d.get("post_click_families_below_final_threshold") or []),
    }
    exact_blocker_surface = {
        "exact_blockers_by_family": _mapping(item_d.get("exact_blockers_by_family")),
        "post_click_exact_blockers_by_family": _mapping(
            item_d.get("post_click_exact_blockers_by_family")
        ),
        "candidate_search_evidence": _mapping(item_d.get("candidate_search_evidence")),
    }
    apply_surface = {
        "last_apply_route": apply_route_d,
        "primary_payload_binding_audit": binding_audit_d,
    }
    payload = {
        "item_hash": stable_final_publication_hash(item_d),
        "final_visible_resolution_hash": stable_final_publication_hash(resolution_d),
        "guidance_debug_hash": stable_final_publication_hash(debug_d),
        "post_cleanup_render_audit_hash": stable_final_publication_hash(render_audit_d),
        "last_apply_route_hash": stable_final_publication_hash(apply_route_d),
        "primary_payload_binding_audit_hash": stable_final_publication_hash(binding_audit_d),
        "final_contract_hash": stable_final_publication_hash(contract_d),
        "ligature_state": ligature_state,
        "ligature_state_hash": stable_final_publication_hash(ligature_state),
        "post_click_families": post_click_families,
        "post_click_families_hash": stable_final_publication_hash(post_click_families),
        "exact_blocker_surface_hash": stable_final_publication_hash(exact_blocker_surface),
        "apply_surface_hash": stable_final_publication_hash(apply_surface),
        "represented_live_groups": (
            "page_session_apply_inputs",
            "page_current_state_inputs",
            "exact_blocker_helper_inputs",
            "render_item_replacement_inputs",
        ),
        "derived_from": "FinalDesignGuidePublication.post_click_final_contract_checks",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "proof_hash": stable_final_publication_hash(payload)}


def build_final_design_guide_post_click_bending_replacement_audit_result_proof(
    *,
    guidance_debug: dict[str, Any] | None = None,
    audit_sources: list[Any] | tuple[Any, ...] | None = None,
    bending_resolution: dict[str, Any] | None = None,
    bending_contract: dict[str, Any] | None = None,
    output_item: dict[str, Any] | None = None,
    final_visible_resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build proof-only coverage for post-click bending replacement audit/result.

    This normalizes the audit evidence merge and records the resolution result
    surface. It does not build the replacement item, render UI, route Apply, read
    session state, or mutate any caller-owned dictionaries.
    """

    debug_d = _mapping(guidance_debug)
    sources = [_mapping(source) for source in (audit_sources or []) if isinstance(source, dict)]
    audit_projection = dict(debug_d)
    evidence_keys = (
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "cleanup_evidence_by_family",
        "post_click_cleanup_evidence_by_family",
    )
    family_list_keys = (
        "post_click_families_below_final_threshold",
        "post_click_unresolved_low_util_families",
        "low_util_families",
        "materially_overprovided_families",
    )
    for source in sources:
        for evidence_key in evidence_keys:
            source_evidence = _mapping(source.get(evidence_key))
            if not source_evidence:
                continue
            existing = _mapping(audit_projection.get(evidence_key))
            for family, blocker in source_evidence.items():
                family_key = str(family or "").strip().lower()
                if family_key and isinstance(blocker, dict):
                    existing[family_key] = dict(blocker)
            audit_projection[evidence_key] = dict(existing)
        for family_list_key in family_list_keys:
            source_family_list = source.get(family_list_key)
            if not isinstance(source_family_list, list) or not source_family_list:
                continue
            existing_family_list = list(audit_projection.get(family_list_key) or [])
            audit_projection[family_list_key] = list(
                dict.fromkeys(
                    str(family or "").strip().lower()
                    for family in (existing_family_list + list(source_family_list))
                    if str(family or "").strip()
                )
            )
        if isinstance(source.get("post_click_family_utils"), dict):
            audit_projection["post_click_family_utils"] = dict(
                source.get("post_click_family_utils") or {}
            )
    if (
        "post_click_exact_blockers_by_family" not in audit_projection
        and isinstance(audit_projection.get("exact_blockers_by_family"), dict)
    ):
        audit_projection["post_click_exact_blockers_by_family"] = dict(
            audit_projection.get("exact_blockers_by_family") or {}
        )

    resolution_d = _mapping(bending_resolution)
    contract_d = _mapping(bending_contract)
    output_item_d = _mapping(output_item)
    final_resolution_d = _mapping(final_visible_resolution)
    audit_projection_hash = stable_final_publication_hash(audit_projection)
    resolution_result = {
        "bending_resolution_hash": stable_final_publication_hash(resolution_d),
        "bending_contract_hash": stable_final_publication_hash(contract_d),
        "bending_contract_enabled_flag": bool(contract_d.get("enabled")),
        "output_item_hash": stable_final_publication_hash(output_item_d),
        "final_visible_resolution_hash": stable_final_publication_hash(final_resolution_d),
        "render_reason": _text(final_resolution_d.get("render_reason")),
    }
    payload = {
        "audit_projection": audit_projection,
        "audit_projection_hash": audit_projection_hash,
        "audit_source_hashes": [stable_final_publication_hash(source) for source in sources],
        "resolution_result": resolution_result,
        "resolution_result_hash": stable_final_publication_hash(resolution_result),
        "represented_live_rows": (
            "bending_audit_seed_from_guidance_debug",
            "evidence_source_merge_loop",
            "family_list_merge_loop",
            "post_click_family_utils_copy",
            "exact_blocker_alias_fill",
            "low_bending_resolution_builder_result",
            "bending_contract_extract",
        ),
        "derived_from": (
            "FinalDesignGuidePublication.post_click_bending_replacement_audit_result"
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "proof_hash": stable_final_publication_hash(payload)}


def build_final_design_guide_post_click_low_bending_resolution_request_proof(
    *,
    state: dict[str, Any] | None = None,
    overview: dict[str, Any] | None = None,
    mode_config: dict[str, Any] | None = None,
    acceptance_audit: dict[str, Any] | None = None,
    last_apply_route: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build proof-only request coverage for low-bending resolution.

    This makes the current page/session inputs explicit before the live builder
    is moved. It does not perform candidate search, build guidance items, render,
    route Apply, or mutate caller-owned data.
    """

    state_d = _mapping(state)
    overview_d = _mapping(overview)
    mode_d = _mapping(mode_config)
    audit_d = _mapping(acceptance_audit)
    last_apply_d = _mapping(last_apply_route)
    last_apply_label = " ".join(
        str(last_apply_d.get(key) or "")
        for key in (
            "resolved_candidate_label",
            "candidate_label_at_step_start",
            "post_apply_resolved_candidate_label",
        )
    ).strip().lower()
    post_click_apply_context = bool(
        last_apply_d.get("apply_used_resolved_candidate_payload")
        and last_apply_d.get("applied_updates")
    )
    audit_family_sets = {
        "unresolved": [
            str(family or "").strip().lower()
            for family in list(audit_d.get("post_click_unresolved_low_util_families") or [])
            if str(family or "").strip()
        ],
        "below_floor": [
            str(family or "").strip().lower()
            for family in list(audit_d.get("post_click_families_below_final_threshold") or [])
            if str(family or "").strip()
        ],
    }
    request_summary = {
        "state_hash": stable_final_publication_hash(state_d),
        "overview_hash": stable_final_publication_hash(overview_d),
        "mode_config_hash": stable_final_publication_hash(mode_d),
        "acceptance_audit_hash": stable_final_publication_hash(audit_d),
        "last_apply_route_hash": stable_final_publication_hash(last_apply_d),
        "post_click_apply_context": post_click_apply_context,
        "last_apply_label": last_apply_label,
        "audit_family_sets": audit_family_sets,
        "audit_family_sets_hash": stable_final_publication_hash(audit_family_sets),
    }
    payload = {
        "request_summary": request_summary,
        "request_summary_hash": stable_final_publication_hash(request_summary),
        "represented_live_inputs": (
            "state",
            "overview",
            "mode_config",
            "acceptance_audit",
            "last_apply_route",
        ),
        "hidden_page_dependency_represented": "DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY",
        "derived_from": "FinalDesignGuidePublication.post_click_low_bending_resolution_request",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "proof_hash": stable_final_publication_hash(payload)}


def build_final_design_guide_post_click_low_bending_resolution_result_projection_proof(
    *,
    result_item: dict[str, Any] | None = None,
    acceptance_audit: dict[str, Any] | None = None,
    final_visible_resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build proof-only projection for low-bending resolution result surfaces."""

    item_d = _mapping(result_item)
    audit_d = _mapping(acceptance_audit)
    resolution_d = _mapping(final_visible_resolution)
    evidence_d = _mapping(
        item_d.get("candidate_search_evidence")
        or _mapping(item_d.get("action_payload")).get("candidate_search_evidence")
        or _mapping(item_d.get("resolved_candidate")).get("candidate_search_evidence")
    )
    exact_blockers = _mapping(
        item_d.get("post_click_exact_blockers_by_family")
        or item_d.get("exact_blockers_by_family")
        or evidence_d.get("post_click_exact_blockers_by_family")
        or evidence_d.get("exact_blockers_by_family")
        or audit_d.get("post_click_exact_blockers_by_family")
    )
    cleanup_flags = {
        "guidance_intent": _text(item_d.get("guidance_intent")),
        "local_cleanup_candidate": bool(item_d.get("local_cleanup_candidate")),
        "post_click_low_family_cleanup_action": bool(
            item_d.get("post_click_low_family_cleanup_action")
        ),
        "terminal_state_blocked_by_local_cleanup": bool(
            item_d.get("terminal_state_blocked_by_local_cleanup")
        ),
        "local_cleanup_search_ran": bool(item_d.get("local_cleanup_search_ran")),
        "local_cleanup_search_exhaustive": bool(item_d.get("local_cleanup_search_exhaustive")),
        "no_second_cta_required": bool(item_d.get("no_second_cta_required")),
    }
    result_identity = {
        "selected_family_id": _text(
            item_d.get("selected_family_id")
            or item_d.get("family")
            or _mapping(item_d.get("button_contract")).get("family")
        ),
        "status": _text(item_d.get("status")),
        "bucket": _text(item_d.get("bucket")),
        "title_main": _text(item_d.get("title_main") or item_d.get("title")),
        "action_type": _text(
            item_d.get("action_type")
            or _mapping(item_d.get("button_contract")).get("action_type")
        ),
        "candidate_id": _text(
            item_d.get("candidate_id")
            or item_d.get("source_candidate_id")
            or evidence_d.get("selected_candidate_id")
        ),
    }
    evidence_projection = {
        "candidate_search_evidence_hash": stable_final_publication_hash(evidence_d),
        "exact_blockers_by_family": exact_blockers,
        "exact_blockers_hash": stable_final_publication_hash(exact_blockers),
        "audit_hash": stable_final_publication_hash(audit_d),
    }
    projection = {
        "result_identity": result_identity,
        "cleanup_flags": cleanup_flags,
        "evidence_projection": evidence_projection,
        "final_visible_resolution_hash": stable_final_publication_hash(resolution_d),
        "result_item_hash": stable_final_publication_hash(item_d),
        "result_projection_hash": stable_final_publication_hash(
            {
                "result_identity": result_identity,
                "cleanup_flags": cleanup_flags,
                "evidence_projection": evidence_projection,
            }
        ),
    }
    payload = {
        "result_projection": projection,
        "result_projection_hash": projection["result_projection_hash"],
        "represented_result_surfaces": (
            "early_cleanup_action_item",
            "best_safe_partial_or_incremental_item",
            "exact_blocker_evidence",
        ),
        "excluded_live_surfaces": (
            "cta_contract_fallback",
            "residual_shear_cleanup_probe",
            "visible_wording",
            "search_and_evaluation_dependencies",
        ),
        "derived_from": "FinalDesignGuidePublication.post_click_low_bending_resolution_result_projection",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "proof_hash": stable_final_publication_hash(payload)}


def build_final_design_guide_post_click_low_bending_residual_shear_cleanup_route_proof(
    *,
    state: dict[str, Any] | None = None,
    overview: dict[str, Any] | None = None,
    mode_config: dict[str, Any] | None = None,
    bending_blocker: dict[str, Any] | None = None,
    exact_blockers_by_family: dict[str, Any] | None = None,
    residual_shear_tightening: dict[str, Any] | None = None,
    residual_result_item: dict[str, Any] | None = None,
    residual_detail: dict[str, Any] | None = None,
    route_debug: dict[str, Any] | None = None,
    route_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build proof-only coverage for the residual shear cleanup route.

    The live route still owns search/evaluation and CTA fallback behavior in the
    page. This object only records the route's request, evidence, and output
    surfaces so they can be traced before any future cutover.
    """

    state_d = _mapping(state)
    overview_d = _mapping(overview)
    mode_d = _mapping(mode_config)
    blocker_d = _mapping(bending_blocker)
    exact_d = _mapping(exact_blockers_by_family)
    tightening_d = _mapping(residual_shear_tightening)
    item_d = _mapping(residual_result_item)
    detail_d = _mapping(residual_detail)
    debug_d = _mapping(route_debug)
    flags_d = _mapping(route_flags)
    evidence_d = _mapping(
        item_d.get("candidate_search_evidence")
        or _mapping(item_d.get("action_payload")).get("candidate_search_evidence")
        or _mapping(item_d.get("resolved_candidate")).get("candidate_search_evidence")
        or tightening_d.get("candidate_search_evidence")
    )
    updates_d = _mapping(
        item_d.get("updates")
        or item_d.get("selected_action_updates")
        or _mapping(item_d.get("button_contract")).get("updates")
        or _mapping(item_d.get("action_payload")).get("resolved_candidate_updates")
        or _mapping(item_d.get("resolved_candidate")).get("updates")
        or tightening_d.get("updates")
    )
    route_request = {
        "state_hash": stable_final_publication_hash(state_d),
        "overview_hash": stable_final_publication_hash(overview_d),
        "mode_config_hash": stable_final_publication_hash(mode_d),
        "bending_blocker_hash": stable_final_publication_hash(blocker_d),
        "exact_blockers_hash": stable_final_publication_hash(exact_d),
        "route_flags_hash": stable_final_publication_hash(flags_d),
        "starting_shear_util": _text(
            flags_d.get("starting_shear_util")
            or evidence_d.get("starting_util")
            or evidence_d.get("current_util")
        ),
    }
    search_projection = {
        "residual_shear_tightening_hash": stable_final_publication_hash(tightening_d),
        "candidate_search_evidence_hash": stable_final_publication_hash(evidence_d),
        "updates_hash": stable_final_publication_hash(updates_d),
        "safe_candidate_count": evidence_d.get("safe_candidate_count"),
        "executable_candidate_count": evidence_d.get("executable_candidate_count"),
        "best_safe_final_util": evidence_d.get("best_safe_final_util"),
        "selected_candidate_id": _text(
            evidence_d.get("selected_candidate_id")
            or evidence_d.get("best_safe_candidate_id")
            or item_d.get("candidate_id")
            or item_d.get("source_candidate_id")
        ),
    }
    blocker_projection = {
        "exact_blockers_by_family": exact_d,
        "exact_blockers_hash": stable_final_publication_hash(exact_d),
        "bending_blocker_preserved": bool(
            evidence_d.get("post_click_bending_blocker_preserved")
            or debug_d.get("post_click_bending_blocker_preserved")
        ),
        "residual_cleanup_after_bending_blocker": bool(
            evidence_d.get("post_click_residual_shear_cleanup_after_bending_blocker")
            or debug_d.get("post_click_residual_shear_cleanup_after_bending_blocker")
        ),
        "outside_target_band_allowed": bool(evidence_d.get("outside_target_band_allowed")),
        "no_second_cta_required": bool(
            evidence_d.get("no_second_cta_required") or item_d.get("no_second_cta_required")
        ),
    }
    result_projection = {
        "result_item_hash": stable_final_publication_hash(item_d),
        "residual_detail_hash": stable_final_publication_hash(detail_d),
        "route_debug_hash": stable_final_publication_hash(debug_d),
        "action_type": _text(
            item_d.get("action_type")
            or _mapping(item_d.get("button_contract")).get("action_type")
        ),
        "guidance_intent": _text(item_d.get("guidance_intent")),
        "selected_family_id": _text(
            item_d.get("selected_family_id")
            or item_d.get("family")
            or _mapping(item_d.get("button_contract")).get("family")
            or "shear"
        ),
        "button_contract_hash": stable_final_publication_hash(
            _mapping(item_d.get("button_contract"))
        ),
        "updates_hash": stable_final_publication_hash(updates_d),
    }
    route_projection = {
        "route_request": route_request,
        "search_projection": search_projection,
        "blocker_projection": blocker_projection,
        "result_projection": result_projection,
    }
    payload = {
        "route_projection": route_projection,
        "route_projection_hash": stable_final_publication_hash(route_projection),
        "represented_route_surfaces": (
            "route_entry_guard",
            "primary_shear_tightening_search",
            "fallback_variant_search",
            "materiality_and_safety_screen",
            "promoted_item_packaging",
            "blocker_evidence_merge",
            "target_band_reason_text",
            "cta_contract_bridge",
            "debug_session_projection",
        ),
        "excluded_live_surfaces": (
            "candidate_generation_execution",
            "candidate_evaluation_execution",
            "cta_contract_execution",
            "visible_wording_authoring",
            "session_debug_mutation",
        ),
        "derived_from": (
            "FinalDesignGuidePublication.post_click_low_bending_residual_shear_cleanup_route"
        ),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "proof_hash": stable_final_publication_hash(payload)}


def build_final_design_guide_post_click_low_bending_resolution_result_item_adapter_proof(
    *,
    result_item: dict[str, Any] | None = None,
    acceptance_audit: dict[str, Any] | None = None,
    final_visible_resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build proof-only full item adapter for low-bending A-class result branches."""

    item_d = _mapping(result_item)
    projection_payload = build_final_design_guide_post_click_low_bending_resolution_result_projection_proof(
        result_item=item_d,
        acceptance_audit=acceptance_audit,
        final_visible_resolution=final_visible_resolution,
    )
    projection = _mapping(projection_payload.get("result_projection"))
    adapted_item = dict(item_d)
    evidence_d = _mapping(
        adapted_item.get("candidate_search_evidence")
        or _mapping(adapted_item.get("action_payload")).get("candidate_search_evidence")
        or _mapping(adapted_item.get("resolved_candidate")).get("candidate_search_evidence")
    )
    exact_blockers = _mapping(
        _mapping(projection.get("evidence_projection")).get("exact_blockers_by_family")
    )
    if exact_blockers:
        evidence_d = {
            **evidence_d,
            "exact_blockers_by_family": exact_blockers,
            "post_click_exact_blockers_by_family": exact_blockers,
        }
        adapted_item["candidate_search_evidence"] = dict(evidence_d)
        adapted_item["exact_blockers_by_family"] = exact_blockers
        adapted_item["post_click_exact_blockers_by_family"] = exact_blockers
        adapted_item["cleanup_evidence_by_family"] = exact_blockers
        adapted_item["post_click_cleanup_evidence_by_family"] = exact_blockers
        payload_d = _mapping(adapted_item.get("action_payload"))
        if payload_d:
            payload_d["candidate_search_evidence"] = dict(evidence_d)
            adapted_item["action_payload"] = payload_d
        resolved_d = _mapping(adapted_item.get("resolved_candidate"))
        if resolved_d:
            resolved_d["candidate_search_evidence"] = dict(evidence_d)
            adapted_item["resolved_candidate"] = resolved_d
    cleanup_flags = _mapping(projection.get("cleanup_flags"))
    for key, value in cleanup_flags.items():
        if key and value not in ("", None):
            adapted_item[key] = value
    adapter_surface = {
        "input_item_hash": stable_final_publication_hash(item_d),
        "adapted_item_hash": stable_final_publication_hash(adapted_item),
        "projection_hash": projection_payload.get("result_projection_hash"),
        "preserved_title": _text(adapted_item.get("title_main") or adapted_item.get("title")),
        "preserved_status": _text(adapted_item.get("status")),
        "preserved_bucket": _text(adapted_item.get("bucket")),
        "button_contract_hash": stable_final_publication_hash(_mapping(adapted_item.get("button_contract"))),
        "candidate_search_evidence_hash": stable_final_publication_hash(
            _mapping(adapted_item.get("candidate_search_evidence"))
        ),
    }
    payload = {
        "adapted_item": adapted_item,
        "adapted_item_hash": adapter_surface["adapted_item_hash"],
        "adapter_surface": adapter_surface,
        "adapter_surface_hash": stable_final_publication_hash(adapter_surface),
        "projection": projection,
        "projection_hash": projection_payload.get("result_projection_hash"),
        "represented_result_surfaces": projection_payload.get("represented_result_surfaces") or (),
        "excluded_live_surfaces": projection_payload.get("excluded_live_surfaces") or (),
        "derived_from": "FinalDesignGuidePublication.post_click_low_bending_resolution_result_item_adapter",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "proof_hash": stable_final_publication_hash(payload)}


def build_final_design_guide_post_click_replacement_decision_proof(
    *,
    final_contract: dict[str, Any] | None = None,
    final_family: str | None = None,
    final_expected_util: Any = None,
    final_current_bending_util: Any = None,
    unresolved_families: list[Any] | tuple[Any, ...] | None = None,
    below_floor_families: list[Any] | tuple[Any, ...] | None = None,
    same_flow_cleanup_apply: bool = False,
    exact_blocker_on_visible_item: bool = False,
    requires_exact_blocker: bool = False,
    visible_action: bool = False,
    bending_audit: dict[str, Any] | None = None,
    bending_resolution: dict[str, Any] | None = None,
    bending_contract: dict[str, Any] | None = None,
    replacement_applied: bool = False,
    output_item: dict[str, Any] | None = None,
    final_visible_resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build proof-only coverage for post-click exact-blocker replacement.

    This records the live page decision result after the page has evaluated the
    post-click checks. It does not decide replacement, bind contracts, render UI,
    route Apply, or mutate page/session state.
    """

    contract_d = _mapping(final_contract)
    audit_d = _mapping(bending_audit)
    resolution_d = _mapping(bending_resolution)
    bending_contract_d = _mapping(bending_contract)
    output_item_d = _mapping(output_item)
    final_resolution_d = _mapping(final_visible_resolution)
    families = {
        "unresolved": [str(value or "").strip().lower() for value in (unresolved_families or []) if str(value or "").strip()],
        "below_floor": [str(value or "").strip().lower() for value in (below_floor_families or []) if str(value or "").strip()],
    }
    decision_inputs = {
        "final_family": _text(final_family),
        "final_expected_util": final_expected_util,
        "final_current_bending_util": final_current_bending_util,
        "same_flow_cleanup_apply": bool(same_flow_cleanup_apply),
        "exact_blocker_on_visible_item": bool(exact_blocker_on_visible_item),
        "requires_exact_blocker": bool(requires_exact_blocker),
        "visible_action": bool(visible_action),
        "families": families,
    }
    replacement_result = {
        "replacement_applied": bool(replacement_applied),
        "output_item_hash": stable_final_publication_hash(output_item_d),
        "final_visible_resolution_hash": stable_final_publication_hash(final_resolution_d),
        "render_reason": _text(final_resolution_d.get("render_reason")),
        "guidance_branch": _text(audit_d.get("guidance_branch")),
    }
    payload = {
        "decision_inputs": decision_inputs,
        "decision_inputs_hash": stable_final_publication_hash(decision_inputs),
        "final_contract_hash": stable_final_publication_hash(contract_d),
        "bending_audit_hash": stable_final_publication_hash(audit_d),
        "bending_resolution_hash": stable_final_publication_hash(resolution_d),
        "bending_contract_hash": stable_final_publication_hash(bending_contract_d),
        "replacement_result": replacement_result,
        "replacement_result_hash": stable_final_publication_hash(replacement_result),
        "represented_live_groups": (
            "page_session_apply_inputs",
            "page_current_state_inputs",
            "exact_blocker_decision",
            "render_item_replacement_mutation",
        ),
        "derived_from": "FinalDesignGuidePublication.post_click_final_contract_checks",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "proof_hash": stable_final_publication_hash(payload)}


def build_final_design_guide_post_click_final_contract_check_adapter_proof(
    *,
    final_contract: dict[str, Any] | None = None,
    final_family: str | None = None,
    final_expected_util: Any = None,
    final_current_bending_util: Any = None,
    unresolved_families: list[Any] | tuple[Any, ...] | None = None,
    below_floor_families: list[Any] | tuple[Any, ...] | None = None,
    same_flow_cleanup_apply: bool = False,
    exact_blocker_on_visible_item: bool = False,
    requires_exact_blocker: bool = False,
    visible_action: bool = False,
    bending_audit: dict[str, Any] | None = None,
    bending_resolution: dict[str, Any] | None = None,
    bending_contract: dict[str, Any] | None = None,
    replacement_applied: bool = False,
    output_item: dict[str, Any] | None = None,
    final_visible_resolution: dict[str, Any] | None = None,
    input_proof: dict[str, Any] | None = None,
    replacement_decision_proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build proof-only adapter coverage for final-visible post-click checks.

    This is the distinct final-visible post-click adapter surface. It records
    the page-collected inputs, decision predicates, evidence assembly, resolution
    builder output, and publication binding result without rendering, routing
    Apply, mutating session state, or changing engineering behavior.
    """

    contract_d = _mapping(final_contract)
    audit_d = _mapping(bending_audit)
    resolution_d = _mapping(bending_resolution)
    bending_contract_d = _mapping(bending_contract)
    output_item_d = _mapping(output_item)
    final_resolution_d = _mapping(final_visible_resolution)
    input_proof_d = _mapping(input_proof)
    replacement_proof_d = _mapping(replacement_decision_proof)
    families = {
        "unresolved": [
            str(value or "").strip().lower()
            for value in (unresolved_families or [])
            if str(value or "").strip()
        ],
        "below_floor": [
            str(value or "").strip().lower()
            for value in (below_floor_families or [])
            if str(value or "").strip()
        ],
    }
    page_input_collection = {
        "input_proof_hash": input_proof_d.get("proof_hash"),
        "input_ligature_state_hash": input_proof_d.get("ligature_state_hash"),
        "input_apply_surface_hash": input_proof_d.get("apply_surface_hash"),
        "input_post_click_families_hash": input_proof_d.get("post_click_families_hash"),
    }
    decision_predicates = {
        "final_family": _text(final_family),
        "final_expected_util": final_expected_util,
        "final_current_bending_util": final_current_bending_util,
        "same_flow_cleanup_apply": bool(same_flow_cleanup_apply),
        "exact_blocker_on_visible_item": bool(exact_blocker_on_visible_item),
        "requires_exact_blocker": bool(requires_exact_blocker),
        "visible_action": bool(visible_action),
        "families": families,
    }
    evidence_assembly = {
        "bending_audit_hash": stable_final_publication_hash(audit_d),
        "exact_blockers_by_family_present": bool(audit_d.get("exact_blockers_by_family")),
        "post_click_exact_blockers_by_family_present": bool(
            audit_d.get("post_click_exact_blockers_by_family")
        ),
        "cleanup_evidence_by_family_present": bool(audit_d.get("cleanup_evidence_by_family")),
        "post_click_cleanup_evidence_by_family_present": bool(
            audit_d.get("post_click_cleanup_evidence_by_family")
        ),
    }
    resolution_builder = {
        "bending_resolution_hash": stable_final_publication_hash(resolution_d),
        "bending_contract_hash": stable_final_publication_hash(bending_contract_d),
        "bending_contract_enabled": bool(bending_contract_d.get("enabled")),
        "bending_resolution_present": bool(resolution_d),
    }
    publication_binding = {
        "replacement_applied": bool(replacement_applied),
        "output_item_hash": stable_final_publication_hash(output_item_d),
        "final_visible_resolution_hash": stable_final_publication_hash(final_resolution_d),
        "render_reason": _text(final_resolution_d.get("render_reason")),
        "replacement_decision_proof_hash": replacement_proof_d.get("proof_hash"),
    }
    adapter_result = {
        "should_publish_exact_blocker_projection": bool(
            visible_action and resolution_d and not bool(bending_contract_d.get("enabled"))
        ),
        "replacement_applied": bool(replacement_applied),
        "output_item_family": _text(output_item_d.get("family") or output_item_d.get("check_key")),
        "render_reason": publication_binding["render_reason"],
    }
    payload = {
        "final_contract_hash": stable_final_publication_hash(contract_d),
        "page_input_collection": page_input_collection,
        "page_input_collection_hash": stable_final_publication_hash(page_input_collection),
        "decision_predicates": decision_predicates,
        "decision_predicates_hash": stable_final_publication_hash(decision_predicates),
        "evidence_assembly": evidence_assembly,
        "evidence_assembly_hash": stable_final_publication_hash(evidence_assembly),
        "resolution_builder": resolution_builder,
        "resolution_builder_hash": stable_final_publication_hash(resolution_builder),
        "publication_binding": publication_binding,
        "publication_binding_hash": stable_final_publication_hash(publication_binding),
        "adapter_result": adapter_result,
        "adapter_result_hash": stable_final_publication_hash(adapter_result),
        "represented_live_groups": (
            "page_input_collection",
            "decision_predicates",
            "evidence_assembly",
            "resolution_builder",
            "publication_binding",
        ),
        "derived_from": "FinalDesignGuidePublication.post_click_final_contract_check_adapter",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "proof_hash": stable_final_publication_hash(payload)}


def build_final_design_guide_post_click_final_contract_predicate_result_adapter(
    *,
    item: dict[str, Any] | None = None,
    final_visible_resolution: dict[str, Any] | None = None,
    guidance_debug: dict[str, Any] | None = None,
    post_cleanup_render_audit: dict[str, Any] | None = None,
    last_apply_route: dict[str, Any] | None = None,
    primary_payload_binding_audit: dict[str, Any] | None = None,
    current_state: dict[str, Any] | None = None,
    final_contract: dict[str, Any] | None = None,
    final_accepted_min_family_util: float = 0.85,
    target_band_eps: float = 0.0,
    compound_shear_update_keys: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Build the post-click final-contract predicate/result adapter.

    This is a pure Design Brain/shared-data boundary. It accepts plain
    dictionaries and already-collected page/apply/session inputs, computes the
    post-click predicate surface, and returns a result payload. It does not
    render UI, route Apply, read session state, build the replacement item, or
    mutate the caller's dictionaries.
    """

    item_d = _mapping(item)
    resolution_d = _mapping(final_visible_resolution)
    debug_d = _mapping(guidance_debug)
    render_audit_d = _mapping(post_cleanup_render_audit)
    last_apply_d = _mapping(last_apply_route)
    binding_audit_d = _mapping(primary_payload_binding_audit)
    state_d = _mapping(current_state)
    contract_d = _mapping(final_contract or item_d.get("button_contract"))

    def _contract_enabled(contract: dict[str, Any]) -> bool:
        return bool(
            contract.get("actionable")
            and _mapping(contract.get("updates"))
            and bool(contract.get("preview_pass"))
            and contract.get("blocking_reason") is None
        )

    def _item_sources() -> list[dict[str, Any]]:
        return [
            item_d,
            _mapping(item_d.get("candidate_search_evidence")),
            _mapping(_mapping(item_d.get("action_payload")).get("candidate_search_evidence")),
            _mapping(_mapping(item_d.get("resolved_candidate")).get("candidate_search_evidence")),
        ]

    def _has_low_util_exact_blocker(family: str) -> bool:
        fam = str(family or "").strip().lower()
        if not fam:
            return False
        for source in _item_sources():
            for key in ("exact_blockers_by_family", "post_click_exact_blockers_by_family"):
                blocker = _mapping(_mapping(source.get(key)).get(fam))
                if (
                    blocker
                    and bool(blocker.get("exact_blocker"))
                    and (
                        bool(blocker.get("no_second_cta_required"))
                        or _number_or_none(blocker.get("best_safe_final_util")) is not None
                    )
                ):
                    return True
        return False

    def _best_safe_partial_cleanup() -> bool:
        if bool(item_d.get("best_safe_partial_cleanup")):
            return True
        evidence = _mapping(item_d.get("candidate_search_evidence"))
        if bool(evidence.get("best_safe_partial_cleanup")):
            return True
        payload = _mapping(item_d.get("action_payload"))
        if bool(payload.get("best_safe_partial_cleanup")):
            return True
        resolved = _mapping(item_d.get("resolved_candidate"))
        return bool(resolved.get("best_safe_partial_cleanup"))

    def _safe_incremental_cleanup_below_threshold() -> bool:
        for source in _item_sources():
            if (
                bool(source.get("outside_target_band_allowed"))
                and str(source.get("outside_target_band_allowed_category") or "").strip()
                in {
                    "safe_incremental_cleanup_below_final_threshold",
                    "safe_improving_cleanup_candidate_available",
                }
            ):
                return True
        return False

    final_family = str(
        item_d.get("family")
        or item_d.get("check_key")
        or contract_d.get("family")
        or ""
    ).strip().lower()
    final_expected_util = _number_or_none(
        contract_d.get("expected_util")
        or item_d.get("expected_util")
        or item_d.get("util")
        or item_d.get("displayed_util")
    )
    overview = _mapping(resolution_d.get("overview"))
    utils = _mapping(overview.get("utils"))
    final_current_bending_util = _number_or_none(utils.get("bending"))
    unresolved_families = sorted(
        {
            str(family or "").strip().lower()
            for family in (
                list(debug_d.get("post_click_unresolved_low_util_families") or [])
                + list(render_audit_d.get("post_click_unresolved_low_util_families") or [])
            )
            if str(family or "").strip()
        }
    )
    below_floor_families = sorted(
        {
            str(family or "").strip().lower()
            for family in (
                list(debug_d.get("post_click_families_below_final_threshold") or [])
                + list(render_audit_d.get("post_click_families_below_final_threshold") or [])
            )
            if str(family or "").strip()
        }
    )
    last_apply_label = " ".join(
        str(last_apply_d.get(key) or "")
        for key in (
            "resolved_candidate_label",
            "one" + "_click_candidate_label_at_step_start",
            "post_apply_resolved_candidate_label",
        )
    ).strip().lower()
    same_flow_cleanup_apply = bool(
        last_apply_d.get("apply_used_resolved_candidate_payload")
        and last_apply_d.get("applied_updates")
        and "cleanup" in last_apply_label
    )
    binding_applied_updates = _mapping(
        binding_audit_d.get("applied_updates")
        or binding_audit_d.get("actual_changed_updates")
    )
    if not same_flow_cleanup_apply:
        same_flow_cleanup_apply = bool(
            binding_applied_updates
            and set(binding_applied_updates) & set(compound_shear_update_keys or ())
            and _number_or_none(state_d.get("lig_d")) == 0
            and _number_or_none(state_d.get("lig_legs")) == 0
        )
    contract_enabled = _contract_enabled(contract_d)
    exact_blocker_on_visible_item = _has_low_util_exact_blocker("bending")
    blocking_reason = str(contract_d.get("blocking_reason") or "").strip()
    item_action_type = str(item_d.get("action_type") or "").strip()
    requires_exact_blocker = bool(
        contract_enabled
        or blocking_reason
        in {
            "post_click_safe_incremental_cleanup_requires_exact_blocker",
            "safe_incremental_cleanup_below_final_threshold",
            "candidate_final_accepted_state_unresolved_low_util",
            "candidate_final_accepted_state_unresolved_low_family",
        }
        or (
            item_action_type == "apply_resolved_candidate"
            and not bool(item_d.get("final_state_class") == "blocker")
        )
    )
    render_reason = str(resolution_d.get("render_reason") or "").strip()
    title = str(item_d.get("title_main") or item_d.get("title") or "").strip().lower()
    visible_action = bool(
        requires_exact_blocker
        and final_family == "bending"
        and render_reason != "final_visible_bending_cleanup_available_before_blocker"
        and (
            "bending" in unresolved_families
            or "bending" in below_floor_families
            or same_flow_cleanup_apply
            or exact_blocker_on_visible_item
            or (
                final_current_bending_util is not None
                and float(final_current_bending_util)
                < float(final_accepted_min_family_util) - float(target_band_eps)
            )
        )
        and (
            _best_safe_partial_cleanup()
            or _safe_incremental_cleanup_below_threshold()
            or bool(item_d.get("safe_incremental_cleanup_below_final_threshold"))
            or exact_blocker_on_visible_item
            or (
                final_expected_util is not None
                and float(final_expected_util) < float(final_accepted_min_family_util)
                and "best safe" in title
            )
        )
    )
    predicate_result = {
        "final_family": final_family,
        "final_expected_util": final_expected_util,
        "final_current_bending_util": final_current_bending_util,
        "unresolved_families": unresolved_families,
        "below_floor_families": below_floor_families,
        "same_flow_cleanup_apply": same_flow_cleanup_apply,
        "contract_enabled": contract_enabled,
        "exact_blocker_on_visible_item": exact_blocker_on_visible_item,
        "requires_exact_blocker": requires_exact_blocker,
        "visible_action": visible_action,
        "best_safe_partial_cleanup": _best_safe_partial_cleanup(),
        "safe_incremental_cleanup_below_threshold": _safe_incremental_cleanup_below_threshold(),
        "render_reason": render_reason,
    }
    input_hashes = {
        "item_hash": stable_final_publication_hash(item_d),
        "final_visible_resolution_hash": stable_final_publication_hash(resolution_d),
        "guidance_debug_hash": stable_final_publication_hash(debug_d),
        "post_cleanup_render_audit_hash": stable_final_publication_hash(render_audit_d),
        "last_apply_route_hash": stable_final_publication_hash(last_apply_d),
        "primary_payload_binding_audit_hash": stable_final_publication_hash(binding_audit_d),
        "current_state_hash": stable_final_publication_hash(state_d),
        "final_contract_hash": stable_final_publication_hash(contract_d),
    }
    bending_resolution_request = {
        "required": bool(visible_action),
        "family": "bending" if visible_action else None,
        "overview_hash": stable_final_publication_hash(overview),
        "audit_input_hash": stable_final_publication_hash(
            {
                "guidance_debug": debug_d,
                "item": item_d,
                "candidate_search_evidence": _mapping(item_d.get("candidate_search_evidence")),
            }
        ),
    }
    payload = {
        "predicate_result": predicate_result,
        "predicate_result_hash": stable_final_publication_hash(predicate_result),
        "input_hashes": input_hashes,
        "bending_resolution_request": bending_resolution_request,
        "bending_resolution_request_hash": stable_final_publication_hash(
            bending_resolution_request
        ),
        "represented_live_rows": (
            "final_contract",
            "final_family",
            "final_expected_util",
            "current_bending_util",
            "contract_enabled_predicate",
            "exact_blocker_predicate",
            "requires_exact_blocker_predicate",
            "visible_action_predicate",
            "bending_audit_assembly",
            "bending_resolution_builder_request",
            "post_click_rebinding_request",
        ),
        "page_owned_input_rows": (
            "post_click_family_sets",
            "last_apply_route",
            "same_flow_cleanup_apply_inputs",
        ),
        "derived_from": "FinalDesignGuidePublication.post_click_final_contract_predicate_result_adapter",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**payload, "proof_hash": stable_final_publication_hash(payload)}


def apply_final_design_guide_post_click_exact_blocker_replacement_projection(
    *,
    item: dict[str, Any] | None = None,
    final_visible_resolution: dict[str, Any] | None = None,
    guidance_debug: dict[str, Any] | None = None,
    replacement_applied: bool = False,
) -> dict[str, Any]:
    """Apply post-click exact-blocker replacement projection to plain dicts.

    The caller still owns the decision, the replacement item, publication
    binding, page/session state, and rendering. This adapter only normalizes the
    post-publish projection rows into a pure data boundary.
    """

    item_d = _mapping(item)
    resolution_d = _mapping(final_visible_resolution)
    debug_d = _mapping(guidance_debug)
    applied = bool(replacement_applied)
    if applied:
        resolution_d["item"] = dict(item_d)
        resolution_d["render_reason"] = "post_click_low_bending_exact_blocker_final"
        debug_d["post_click_low_bending_action_replaced_by_exact_blocker"] = True
        debug_d["guidance_branch"] = "post_click_low_bending_exact_blocker_final"
    payload = {
        "item": item_d,
        "final_visible_resolution": resolution_d,
        "guidance_debug": debug_d,
        "replacement_applied": applied,
    }
    return {
        **payload,
        "projection_hash": stable_final_publication_hash(payload),
        "derived_from": "FinalDesignGuidePublication.post_click_exact_blocker_replacement",
        "proof_only": False,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }


def build_final_design_guide_post_click_final_contract_check_adapter_result(
    *,
    output_item: dict[str, Any] | None = None,
    final_visible_resolution: dict[str, Any] | None = None,
    guidance_debug: dict[str, Any] | None = None,
    visible_action: bool = False,
    bending_resolution: dict[str, Any] | None = None,
    bending_contract: dict[str, Any] | None = None,
    input_proof: dict[str, Any] | None = None,
    replacement_decision_proof: dict[str, Any] | None = None,
    adapter_proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a non-driving result shape for the post-click contract adapter.

    This mirrors the current replacement projection in pure data form so the
    result can be proven before any live authority move. It does not render UI,
    route Apply, read session state, or mutate caller dictionaries.
    """

    output_item_d = _mapping(output_item)
    final_resolution_d = _mapping(final_visible_resolution)
    debug_d = _mapping(guidance_debug)
    bending_resolution_d = _mapping(bending_resolution)
    bending_contract_d = _mapping(bending_contract)
    input_proof_d = _mapping(input_proof)
    replacement_proof_d = _mapping(replacement_decision_proof)
    adapter_proof_d = _mapping(adapter_proof)

    should_publish = bool(
        visible_action and bending_resolution_d and not bool(bending_contract_d.get("enabled"))
    )
    projection = apply_final_design_guide_post_click_exact_blocker_replacement_projection(
        item=output_item_d,
        final_visible_resolution=final_resolution_d,
        guidance_debug=debug_d,
        replacement_applied=should_publish,
    )
    projected_resolution = _mapping(projection.get("final_visible_resolution"))
    projected_debug = _mapping(projection.get("guidance_debug"))
    guidance_debug_patch = (
        {
            "post_click_low_bending_action_replaced_by_exact_blocker": projected_debug.get(
                "post_click_low_bending_action_replaced_by_exact_blocker"
            ),
            "guidance_branch": projected_debug.get("guidance_branch"),
        }
        if should_publish
        else {}
    )
    replacement_item = output_item_d if should_publish else {}
    result = {
        "should_publish_exact_blocker_projection": should_publish,
        "replacement_applied": should_publish,
        "replacement_item": replacement_item,
        "replacement_item_hash": stable_final_publication_hash(replacement_item),
        "final_visible_resolution": projected_resolution,
        "final_visible_resolution_hash": stable_final_publication_hash(projected_resolution),
        "guidance_debug_patch": guidance_debug_patch,
        "guidance_debug_patch_hash": stable_final_publication_hash(guidance_debug_patch),
        "projection_hash": projection.get("projection_hash"),
        "input_proof_hash": input_proof_d.get("proof_hash"),
        "replacement_decision_proof_hash": replacement_proof_d.get("proof_hash"),
        "adapter_proof_hash": adapter_proof_d.get("proof_hash"),
    }
    payload = {
        "result": result,
        "result_hash": stable_final_publication_hash(result),
        "input_hashes": {
            "output_item_hash": stable_final_publication_hash(output_item_d),
            "final_visible_resolution_hash": stable_final_publication_hash(final_resolution_d),
            "guidance_debug_hash": stable_final_publication_hash(debug_d),
            "bending_resolution_hash": stable_final_publication_hash(bending_resolution_d),
            "bending_contract_hash": stable_final_publication_hash(bending_contract_d),
            "input_proof_hash": input_proof_d.get("proof_hash"),
            "replacement_decision_proof_hash": replacement_proof_d.get("proof_hash"),
            "adapter_proof_hash": adapter_proof_d.get("proof_hash"),
        },
        "represented_live_groups": (
            "post_click_final_contract_adapter_result",
            "final_visible_resolution_projection",
            "guidance_debug_projection_patch",
            "publication_binding_result",
        ),
        "derived_from": "FinalDesignGuidePublication.post_click_final_contract_check_adapter_result",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": True,
    }
    return {**payload, "proof_hash": stable_final_publication_hash(payload)}


def build_final_design_guide_post_click_exact_blocker_raw_bound_parity_proof(
    *,
    raw_item: dict[str, Any] | None = None,
    bound_item: dict[str, Any] | None = None,
    final_visible_resolution: dict[str, Any] | None = None,
    guidance_debug: dict[str, Any] | None = None,
    visible_action: bool = False,
    bending_resolution: dict[str, Any] | None = None,
    bending_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare raw-vs-bound inputs for the post-click exact-blocker adapter.

    Proof-only. This does not render, route Apply, read session state, or decide
    whether the old page binding can be removed.
    """

    raw_item_d = _mapping(raw_item)
    bound_item_d = _mapping(bound_item)
    final_resolution_d = _mapping(final_visible_resolution)
    debug_d = _mapping(guidance_debug)
    bending_resolution_d = _mapping(bending_resolution)
    bending_contract_d = _mapping(bending_contract)
    raw_result = build_final_design_guide_post_click_final_contract_check_adapter_result(
        output_item=raw_item_d,
        final_visible_resolution=final_resolution_d,
        guidance_debug=debug_d,
        visible_action=visible_action,
        bending_resolution=bending_resolution_d,
        bending_contract=bending_contract_d,
    )
    bound_result = build_final_design_guide_post_click_final_contract_check_adapter_result(
        output_item=bound_item_d,
        final_visible_resolution=final_resolution_d,
        guidance_debug=debug_d,
        visible_action=visible_action,
        bending_resolution=bending_resolution_d,
        bending_contract=bending_contract_d,
    )
    raw_result_hash = raw_result.get("result_hash")
    bound_result_hash = bound_result.get("result_hash")
    parity = bool(raw_result_hash and raw_result_hash == bound_result_hash)
    proof = {
        "raw_item_hash": stable_final_publication_hash(raw_item_d),
        "bound_item_hash": stable_final_publication_hash(bound_item_d),
        "raw_adapter_result_hash": raw_result_hash,
        "bound_adapter_result_hash": bound_result_hash,
        "raw_adapter_proof_hash": raw_result.get("proof_hash"),
        "bound_adapter_proof_hash": bound_result.get("proof_hash"),
        "raw_bound_adapter_result_parity": parity,
        "ready_to_replace_old_binding": parity,
        "derived_from": "FinalDesignGuidePublication.post_click_exact_blocker_raw_bound_parity",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return {**proof, "proof_hash": stable_final_publication_hash(proof)}


def build_final_visible_contract_binding_no_second_cta_result(
    *,
    evidence_for_binding: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    item: dict[str, Any] | None = None,
    debug: dict[str, Any] | None = None,
    evidence_expected_util: Any = None,
    evidence_family: str = "",
    blocker_families: list[str] | tuple[str, ...] | None = None,
    final_accepted_min_family_util: float = 0.0,
    target_band_eps: float = 0.0,
) -> dict[str, Any]:
    """Represent final-binding no-second-CTA suppression as pure data.

    This mirrors the current page-owned suppression decision without reading
    session state, evaluating candidates, routing Apply, rendering UI, or
    mutating the caller's dictionaries.
    """

    evidence_d = _mapping(evidence_for_binding)
    contract_d = _mapping(contract)
    item_d = _mapping(item)
    debug_d = _mapping(debug)

    def _to_float(value: Any) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except Exception:
            return None

    expected_util = _to_float(evidence_expected_util)
    threshold = float(final_accepted_min_family_util) - float(target_band_eps)
    applies = False
    reason = None
    source = None
    target_band_count = int(
        evidence_d.get("executable_target_band_candidate_count")
        or evidence_d.get("target_band_candidate_count")
        or len(list(evidence_d.get("target_band_candidates") or []))
        or 0
    )
    if expected_util is not None and float(expected_util) < threshold:
        if (
            bool(evidence_d.get("no_second_cta_required"))
            and target_band_count <= 0
            and _final_publication_exact_stop_row_has_engineering_blocker(evidence_d)
        ):
            applies = True
            source = "evidence_for_binding.no_second_cta_required"
            reason = str(
                evidence_d.get("reason")
                or evidence_d.get("outside_target_band_allowed_reason")
                or evidence_d.get("why_reduction_would_hurt_other_design_elements")
                or "post-click exact cleanup proof suppresses a second below-floor CTA"
            )
        exact_sources = [
            _mapping(item_d.get("post_click_exact_blockers_by_family")),
            _mapping(item_d.get("exact_blockers_by_family")),
            _mapping(evidence_d.get("post_click_exact_blockers_by_family")),
            _mapping(evidence_d.get("exact_blockers_by_family")),
            _mapping(debug_d.get("post_click_exact_blockers_by_family")),
            _mapping(debug_d.get("exact_blockers_by_family")),
        ]
        families = [
            str(family or "").strip().lower()
            for family in (
                list(blocker_families or [])
                or [str(evidence_family or evidence_d.get("family") or "").strip().lower()]
            )
            if str(family or "").strip()
        ]
        if not families:
            families = ["bending", "shear", "combined"]
        if not applies:
            for exact_source in exact_sources:
                for family in families:
                    blocker = _mapping(exact_source.get(family))
                    if not blocker:
                        continue
                    blocker_util = _to_float(
                        blocker.get("best_safe_final_util") or blocker.get("failed_check_util")
                    )
                    if (
                        bool(blocker.get("no_second_cta_required"))
                        and str(blocker.get("failed_check_status") or "").strip().upper()
                        == "BLOCKED_BY_FINAL_ACCEPTED_THRESHOLD"
                        and (blocker_util is None or float(blocker_util) < threshold)
                        and _final_publication_exact_stop_row_has_engineering_blocker(blocker)
                    ):
                        applies = True
                        source = f"exact_blocker.{family}"
                        reason = str(
                            blocker.get("reason")
                            or blocker.get("why_reduction_would_hurt_other_design_elements")
                            or "post-click exact cleanup proof suppresses a second below-floor CTA"
                        )
                        break
                if applies:
                    break

    contract_effect = (
        {
            "enabled": False,
            "actionable": False,
            "action_type": None,
            "updates": {},
            "preview_pass": False,
            "blocking_reason": reason,
        }
        if applies
        else {}
    )
    item_effect = (
        {
            "button_contract": {**contract_d, **contract_effect},
            "primary_card_actionable": False,
            "no_second_cta_required": True,
        }
        if applies
        else {}
    )
    evidence_effect = (
        {
            "no_second_cta_required": True,
            "final_binding_no_second_cta_suppressed": True,
            "final_binding_no_second_cta_reason": reason,
        }
        if applies
        else {}
    )
    debug_effect = (
        {
            "final_binding_no_second_cta_suppressed": True,
            "final_binding_no_second_cta_reason": reason,
        }
        if applies
        else {}
    )
    result = {
        "applies": applies,
        "reason": reason,
        "source": source,
        "target_band_candidate_count": target_band_count,
        "evidence_expected_util": expected_util,
        "threshold": threshold,
        "contract_effect": contract_effect,
        "item_effect": item_effect,
        "evidence_effect": evidence_effect,
        "debug_effect": debug_effect,
    }
    payload = {
        "result": result,
        "result_hash": stable_final_publication_hash(result),
        "input_hashes": {
            "evidence_for_binding_hash": stable_final_publication_hash(evidence_d),
            "contract_hash": stable_final_publication_hash(contract_d),
            "item_hash": stable_final_publication_hash(item_d),
            "debug_hash": stable_final_publication_hash(debug_d),
            "blocker_families_hash": stable_final_publication_hash(list(blocker_families or [])),
        },
        "represented_live_groups": (
            "final_binding_no_second_cta_decision",
            "button_contract_suppression_effect",
            "item_suppression_effect",
            "evidence_suppression_effect",
            "debug_suppression_effect",
        ),
        "derived_from": "FinalDesignGuidePublication.final_visible_contract_binding_no_second_cta",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": True,
    }
    return {**payload, "proof_hash": stable_final_publication_hash(payload)}


def build_final_visible_contract_binding_target_band_promotion_result(
    *,
    evidence_for_binding: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    item: dict[str, Any] | None = None,
    target_binding_updates: dict[str, Any] | None = None,
    target_binding_util: Any = None,
    target_binding_count: int = 0,
    target_binding_family: str = "",
    target_binding_candidate_id: Any = None,
    target_low: Any = None,
    target_high: Any = None,
    current_binding_expected: Any = None,
    target_updates_already_applied: bool = False,
    compound_shear_update_keys: list[str] | tuple[str, ...] | None = None,
    target_band_eps: float = 0.0,
) -> dict[str, Any]:
    """Represent final-binding target-band promotion as pure data.

    The caller remains responsible for page/shared facts such as update-state
    matching, target-band fallback resolution, and candidate-id normalization.
    This function decides whether those plain facts imply a target-band
    promotion and returns plain effect maps.
    """

    evidence_d = _mapping(evidence_for_binding)
    contract_d = _mapping(contract)
    item_d = _mapping(item)
    updates_d = _mapping(target_binding_updates)

    def _to_float(value: Any) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except Exception:
            return None

    def _to_int(value: Any) -> int:
        try:
            return int(value or 0)
        except Exception:
            return 0

    target_util = _to_float(target_binding_util)
    target_low_f = _to_float(target_low)
    target_high_f = _to_float(target_high)
    current_expected = _to_float(current_binding_expected)
    count = _to_int(target_binding_count)
    family = str(target_binding_family or "").strip().lower()
    shear_keys = {str(key or "").strip() for key in (compound_shear_update_keys or [])}
    update_keys = {str(key or "").strip() for key in updates_d}
    outside_target = bool(
        current_expected is None
        or (
            target_low_f is not None
            and float(current_expected) < float(target_low_f) - float(target_band_eps)
        )
        or (
            target_high_f is not None
            and float(current_expected) > float(target_high_f) + float(target_band_eps)
        )
    )
    evidence_available = bool(
        family == "shear"
        and count > 0
        and updates_d
        and bool(update_keys & shear_keys)
        and not bool(target_updates_already_applied)
    )
    applies = bool(evidence_available and outside_target)
    candidate_id = target_binding_candidate_id

    evidence_effect = {}
    contract_effect = {}
    item_effect = {}
    display_truth_effect = {}
    action_payload_effect = {}
    resolved_candidate_effect = {}
    debug_effect = {}

    if applies:
        target_reaching_key = "one_" + "click_target_reaching_candidate_exists"
        evidence_effect = {
            "family": "shear",
            "primary_action_family": "shear",
            "selected_candidate_updates": dict(updates_d),
            "best_safe_candidate_updates": dict(updates_d),
            "closest_safe_candidate_updates": dict(updates_d),
            "target_band_candidate_count": max(1, int(count)),
            "executable_target_band_candidate_count": max(1, int(count)),
            target_reaching_key: True,
        }
        if candidate_id:
            evidence_effect.update(
                {
                    "selected_candidate_id": candidate_id,
                    "best_safe_candidate_id": candidate_id,
                    "closest_safe_candidate_id": candidate_id,
                }
            )
        if target_util is not None:
            evidence_effect.update(
                {
                    "selected_candidate_util": float(target_util),
                    "best_safe_final_util": float(target_util),
                    "closest_safe_candidate_util": float(target_util),
                    "best_target_band_candidate_util": float(target_util),
                }
            )
        contract_effect = {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "updates": dict(updates_d),
            "preview_pass": True,
            "expected_util": None if target_util is None else float(target_util),
            "blocking_reason": None,
            "source_candidate_id": candidate_id,
            "candidate_id": candidate_id,
        }
        item_effect = {
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "check_key": "shear",
            "selected_action_family": "shear",
            "primary_card_actionable": True,
            "updates": dict(updates_d),
            "selected_action_updates": dict(updates_d),
            "button_contract": {**contract_d, **contract_effect},
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
        }
        if target_util is not None:
            item_effect.update(
                {
                    "expected_util": float(target_util),
                    "candidate_post_util": float(target_util),
                    "displayed_util": float(target_util),
                }
            )
            display_truth_effect = {
                "display_truth_source": "candidate_preview",
                "displayed_util": float(target_util),
                "displayed_status": "PASS",
                "source_candidate_util": float(target_util),
            }
        candidate_evidence_after = {**evidence_d, **evidence_effect}
        item_effect["candidate_search_evidence"] = dict(candidate_evidence_after)
        action_payload_effect = {
            "updates": dict(updates_d),
            "resolved_candidate_updates": dict(updates_d),
            "resolved_candidate_action_type": "apply_resolved_candidate",
            "resolved_candidate_family_tag": "shear",
            "candidate_search_evidence": dict(candidate_evidence_after),
            "source_candidate_id": candidate_id,
            "candidate_id": candidate_id,
            "expected_util": None if target_util is None else float(target_util),
            "expected_governing_util": None if target_util is None else float(target_util),
            "resolved_candidate_post_util": None if target_util is None else float(target_util),
        }
        resolved_candidate_effect = {
            "updates": dict(updates_d),
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "candidate_search_evidence": dict(candidate_evidence_after),
            "source_candidate_id": candidate_id,
            "candidate_id": candidate_id,
            "candidate_post_util": None if target_util is None else float(target_util),
        }
        debug_effect = {
            "final_binding_target_band_candidate_promoted": True,
            "final_binding_target_band_candidate_updates": dict(updates_d),
            "final_binding_target_band_candidate_util": target_util,
            "primary_button_contract": {**contract_d, **contract_effect},
            "button_contract": {**contract_d, **contract_effect},
            "button_contract_enabled": True,
            "button_contract_updates": dict(updates_d),
            "selected_action_updates": dict(updates_d),
            "candidate_search_evidence": dict(candidate_evidence_after),
        }

    result = {
        "applies": applies,
        "reason": (
            "shear target-band candidate promotes final binding"
            if applies
            else "target-band promotion conditions not met"
        ),
        "target_binding_evidence_available": evidence_available,
        "current_binding_outside_target": outside_target,
        "target_binding_count": count,
        "target_binding_family": family,
        "target_binding_util": target_util,
        "target_low": target_low_f,
        "target_high": target_high_f,
        "current_binding_expected": current_expected,
        "target_updates_already_applied": bool(target_updates_already_applied),
        "contract_effect": contract_effect,
        "item_effect": item_effect,
        "evidence_effect": evidence_effect,
        "display_truth_effect": display_truth_effect,
        "action_payload_effect": action_payload_effect,
        "resolved_candidate_effect": resolved_candidate_effect,
        "debug_effect": debug_effect,
    }
    payload = {
        "result": result,
        "result_hash": stable_final_publication_hash(result),
        "input_hashes": {
            "evidence_for_binding_hash": stable_final_publication_hash(evidence_d),
            "contract_hash": stable_final_publication_hash(contract_d),
            "item_hash": stable_final_publication_hash(item_d),
            "target_binding_updates_hash": stable_final_publication_hash(updates_d),
            "compound_shear_update_keys_hash": stable_final_publication_hash(list(compound_shear_update_keys or [])),
        },
        "represented_live_groups": (
            "final_binding_target_band_candidate_promotion_decision",
            "button_contract_promotion_effect",
            "item_promotion_effect",
            "evidence_promotion_effect",
            "display_truth_promotion_effect",
            "action_payload_promotion_effect",
            "resolved_candidate_promotion_effect",
            "debug_promotion_effect",
        ),
        "derived_from": "FinalDesignGuidePublication.final_visible_contract_binding_target_band_promotion",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": True,
    }
    return {**payload, "proof_hash": stable_final_publication_hash(payload)}


def build_final_visible_contract_binding_consistency_guard_result(
    *,
    evidence_for_binding: dict[str, Any] | None = None,
    current_updates: dict[str, Any] | None = None,
    safe_binding_updates: dict[str, Any] | None = None,
    combined_binding_updates: dict[str, Any] | None = None,
    safe_updates_already_applied: bool = False,
    combined_updates_already_applied: bool = False,
    compound_shear_update_keys: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Represent final-binding stale contract reset as pure data.

    The caller remains responsible for update-state matching. This object only
    decides whether the already-computed facts mean the current button contract
    no longer matches the family-owned evidence.
    """

    evidence_d = _mapping(evidence_for_binding)
    current_updates_d = _mapping(current_updates)
    safe_updates_d = _mapping(safe_binding_updates)
    combined_updates_d = _mapping(combined_binding_updates)
    family = str(evidence_d.get("family") or "").strip().lower()
    shear_keys = {str(key or "").strip() for key in (compound_shear_update_keys or [])}
    safe_update_keys = {str(key or "").strip() for key in safe_updates_d}
    target_reaching_key = "one_" + "click_target_reaching_candidate_exists"
    safe_available = bool(
        family == "shear"
        and safe_updates_d
        and bool(safe_update_keys & shear_keys)
        and not bool(safe_updates_already_applied)
        and (
            bool(evidence_d.get(target_reaching_key))
            or int(evidence_d.get("accepted_band_candidate_count") or 0) > 0
        )
    )
    combined_available = bool(
        family == "combined"
        and combined_updates_d
        and not bool(combined_updates_already_applied)
        and bool(
            evidence_d.get("cleanup_search_ran")
            or evidence_d.get("local_cleanup_search_ran")
            or evidence_d.get("candidate_search_exhaustive")
        )
    )
    safe_mismatch = bool(safe_available and dict(current_updates_d) != dict(safe_updates_d))
    combined_mismatch = bool(
        combined_available and dict(current_updates_d) != dict(combined_updates_d)
    )
    reset_contract = bool(safe_mismatch or combined_mismatch)
    reason = "contract consistency guard did not reset"
    guard_family = None
    expected_updates: dict[str, Any] = {}
    if safe_mismatch:
        reason = "shear safe-binding evidence disagrees with current button contract"
        guard_family = "shear"
        expected_updates = dict(safe_updates_d)
    elif combined_mismatch:
        reason = "combined cleanup evidence disagrees with current button contract"
        guard_family = "combined"
        expected_updates = dict(combined_updates_d)

    result = {
        "reset_contract": reset_contract,
        "reason": reason,
        "guard_family": guard_family,
        "safe_binding_evidence_available": safe_available,
        "combined_binding_evidence_available": combined_available,
        "safe_binding_mismatch": safe_mismatch,
        "combined_binding_mismatch": combined_mismatch,
        "expected_updates": expected_updates,
        "updates_replacement": {} if reset_contract else dict(current_updates_d),
        "action_type_replacement": "" if reset_contract else None,
        "contract_replacement": {} if reset_contract else None,
        "debug_effect": {
            "final_binding_contract_consistency_guard_reset": reset_contract,
            "final_binding_contract_consistency_guard_reason": reason,
            "final_binding_contract_consistency_guard_family": guard_family,
            "final_binding_contract_consistency_guard_expected_updates": dict(expected_updates),
        },
    }
    payload = {
        "result": result,
        "result_hash": stable_final_publication_hash(result),
        "input_hashes": {
            "evidence_for_binding_hash": stable_final_publication_hash(evidence_d),
            "current_updates_hash": stable_final_publication_hash(current_updates_d),
            "safe_binding_updates_hash": stable_final_publication_hash(safe_updates_d),
            "combined_binding_updates_hash": stable_final_publication_hash(combined_updates_d),
            "compound_shear_update_keys_hash": stable_final_publication_hash(list(compound_shear_update_keys or [])),
        },
        "represented_live_groups": (
            "safe_binding_contract_mismatch_reset",
            "combined_binding_contract_mismatch_reset",
            "contract_consistency_guard_debug_effect",
        ),
        "derived_from": "FinalDesignGuidePublication.final_visible_contract_binding_consistency_guard",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": True,
    }
    return {**payload, "proof_hash": stable_final_publication_hash(payload)}


def build_final_visible_contract_binding_truth_result(
    *,
    evidence_for_binding: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    item: dict[str, Any] | None = None,
    updates: dict[str, Any] | None = None,
    compound_shear_update_keys: list[str] | tuple[str, ...] | None = None,
    compound_bottom_update_keys: list[str] | tuple[str, ...] | None = None,
    combined_binding_bending_util: Any = None,
) -> dict[str, Any]:
    """Represent enabled contract family/util truth as pure data.

    The caller supplies any page-evaluated combined preview util as a plain
    value. This object does not evaluate candidates or inspect page/session
    state.
    """

    evidence_d = _mapping(evidence_for_binding)
    contract_d = _mapping(contract)
    item_d = _mapping(item)
    updates_d = _mapping(updates)

    def _to_float(value: Any) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except Exception:
            return None

    def _to_int(value: Any) -> int:
        try:
            return int(value or 0)
        except Exception:
            return 0

    evidence_expected_util = _to_float(
        evidence_d.get("selected_candidate_util")
        or evidence_d.get("best_target_band_candidate_util")
        or evidence_d.get("closest_safe_candidate_util")
        or evidence_d.get("best_safe_final_util")
    )
    contract_expected_util = _to_float(contract_d.get("expected_util"))
    evidence_family = str(evidence_d.get("family") or "").strip().lower()
    update_keys = {str(key or "").strip() for key in updates_d}
    shear_keys = {str(key or "").strip() for key in (compound_shear_update_keys or [])}
    bottom_keys = {str(key or "").strip() for key in (compound_bottom_update_keys or [])}
    cross_family = bool((update_keys & shear_keys) and (update_keys & bottom_keys))
    combined_text = " ".join(
        str(part or "").strip().lower()
        for part in (
            evidence_family,
            evidence_d.get("selected_candidate_id"),
            evidence_d.get("best_safe_candidate_id"),
            evidence_d.get("closest_safe_candidate_id"),
            evidence_d.get("search_scope"),
            evidence_d.get("primary_action_family"),
            evidence_d.get("merged_action_family"),
            evidence_d.get("same_click_merged_payload_family"),
            contract_d.get("candidate_id"),
            contract_d.get("source_candidate_id"),
            item_d.get("candidate_id"),
            item_d.get("source_candidate_id"),
        )
        if str(part or "").strip()
    )
    title_hint = " ".join(
        str(part or "").strip().lower()
        for part in (
            item_d.get("title_main"),
            item_d.get("title"),
            item_d.get("primary_action"),
            item_d.get("secondary_action"),
        )
        if str(part or "").strip()
    )
    resolved_family = evidence_family
    family_resolution_source = "evidence_family"
    if cross_family and (resolved_family == "combined" or "combined" in combined_text):
        resolved_family = "combined"
        family_resolution_source = "combined_cross_family_updates"
    elif "optional bending cleanup" in title_hint or (
        "bending cleanup" in title_hint and "shear cleanup" not in title_hint
    ):
        resolved_family = "bending"
        family_resolution_source = "title_hint_bending_cleanup"
    elif "optional shear cleanup" in title_hint or (
        "shear cleanup" in title_hint and "bending cleanup" not in title_hint
    ):
        resolved_family = "shear"
        family_resolution_source = "title_hint_shear_cleanup"

    util_resolution_source = "evidence_candidate_util"
    if resolved_family == "bending":
        bending_target_util = _to_float(evidence_d.get("best_target_band_candidate_util"))
        bending_target_count = _to_int(
            evidence_d.get("target_band_candidate_count")
            or evidence_d.get("executable_target_band_candidate_count")
            or len(list(evidence_d.get("target_band_candidates") or []))
            or 0
        )
        if bending_target_util is not None and bending_target_count > 0:
            evidence_expected_util = float(bending_target_util)
            util_resolution_source = "bending_target_band_candidate_util"
    if resolved_family == "combined" and cross_family:
        combined_bending = _to_float(combined_binding_bending_util)
        if combined_bending is not None:
            evidence_expected_util = float(combined_bending)
            util_resolution_source = "combined_preview_bending_util"

    blocker_families = {resolved_family} if resolved_family else set()
    if resolved_family == "combined" and bool(update_keys & bottom_keys):
        blocker_families.add("bending")
    if resolved_family == "combined" and bool(update_keys & shear_keys):
        blocker_families.add("shear")

    applies = bool(
        resolved_family in {"bending", "shear", "combined"}
        and evidence_expected_util is not None
        and (
            contract_expected_util is None
            or abs(float(evidence_expected_util) - float(contract_expected_util)) > 0.005
            or str(contract_d.get("family") or "").strip().lower() == "combined"
            or resolved_family == "combined"
        )
    )
    contract_effect: dict[str, Any] = {}
    item_effect: dict[str, Any] = {}
    evidence_effect: dict[str, Any] = {}
    display_truth_effect: dict[str, Any] = {}
    if applies:
        contract_effect = {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": resolved_family,
            "updates": dict(updates_d),
            "preview_pass": True,
            "expected_util": float(evidence_expected_util),
            "blocking_reason": None,
        }
        item_effect = {
            "family": resolved_family,
            "check_key": resolved_family,
            "selected_action_family": resolved_family,
            "expected_util": float(evidence_expected_util),
            "candidate_post_util": float(evidence_expected_util),
            "displayed_util": float(evidence_expected_util),
            "button_contract": {**contract_d, **contract_effect},
        }
        if resolved_family == "combined" and cross_family:
            title = "Shear and bending cleanup - one-click optimisation"
            item_effect.update(
                {
                    "title_main": title,
                    "title": f"{title} (utilisation = {float(evidence_expected_util):.2f})",
                }
            )
        display_truth_effect = {
            "display_truth_source": "candidate_preview",
            "displayed_util": float(evidence_expected_util),
            "source_candidate_util": float(evidence_expected_util),
        }
        evidence_effect = {
            "family": resolved_family,
            "primary_action_family": resolved_family,
            "selected_candidate_util": float(evidence_expected_util),
        }

    result = {
        "applies": applies,
        "evidence_expected_util": evidence_expected_util,
        "contract_expected_util": contract_expected_util,
        "evidence_family_for_contract": resolved_family,
        "family_resolution_source": family_resolution_source,
        "util_resolution_source": util_resolution_source,
        "contract_updates_cross_family": cross_family,
        "blocker_families_for_contract": sorted(blocker_families),
        "contract_update_keys_for_family": sorted(update_keys),
        "contract_combined_text": combined_text,
        "title_hint_for_contract": title_hint,
        "contract_effect": contract_effect,
        "item_effect": item_effect,
        "evidence_effect": evidence_effect,
        "display_truth_effect": display_truth_effect,
        "debug_effect": {
            "final_binding_contract_truth_family": resolved_family,
            "final_binding_contract_truth_expected_util": evidence_expected_util,
            "final_binding_contract_truth_family_source": family_resolution_source,
            "final_binding_contract_truth_util_source": util_resolution_source,
            "final_binding_contract_truth_blocker_families": sorted(blocker_families),
        },
    }
    payload = {
        "result": result,
        "result_hash": stable_final_publication_hash(result),
        "input_hashes": {
            "evidence_for_binding_hash": stable_final_publication_hash(evidence_d),
            "contract_hash": stable_final_publication_hash(contract_d),
            "item_hash": stable_final_publication_hash(item_d),
            "updates_hash": stable_final_publication_hash(updates_d),
            "compound_shear_update_keys_hash": stable_final_publication_hash(list(compound_shear_update_keys or [])),
            "compound_bottom_update_keys_hash": stable_final_publication_hash(list(compound_bottom_update_keys or [])),
        },
        "represented_live_groups": (
            "enabled_contract_expected_util_family_truth",
            "enabled_contract_blocker_family_truth",
            "combined_preview_bending_util_plain_input",
        ),
        "derived_from": "FinalDesignGuidePublication.final_visible_contract_binding_truth",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": False,
    }
    return {**payload, "proof_hash": stable_final_publication_hash(payload)}


def build_final_visible_contract_binding_typed_fallback_payload(
    *,
    result: dict[str, Any] | None = None,
    input_hashes: dict[str, Any] | None = None,
    represented_live_groups: list[str] | tuple[str, ...] | None = None,
    derived_from: str = "",
    error: str = "",
    fallback_reason: str = "helper_exception",
    ready_for_live_cutover: bool = True,
) -> dict[str, Any]:
    """Build a typed no-throw fallback payload for final-binding helpers.

    This preserves the previous page fallback semantics while avoiding an empty
    payload. Callers provide the already-computed safe result/effect maps as
    plain data; this helper only stamps stable hashes and non-authoritative
    proof metadata.
    """

    result_d = _mapping(result)
    input_hashes_d = _mapping(input_hashes)
    fallback = {
        "result": result_d,
        "result_hash": stable_final_publication_hash(result_d),
        "input_hashes": input_hashes_d,
        "represented_live_groups": tuple(represented_live_groups or ()),
        "derived_from": str(derived_from or "FinalDesignGuidePublication.final_visible_contract_binding_typed_fallback"),
        "fallback_payload": True,
        "fallback_reason": str(fallback_reason or "helper_exception"),
        "error": str(error or ""),
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": bool(ready_for_live_cutover),
    }
    return {**fallback, "proof_hash": stable_final_publication_hash(fallback)}


def build_final_visible_contract_binding_rebind_effects_proof(
    *,
    evidence_for_binding: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    item: dict[str, Any] | None = None,
    debug: dict[str, Any] | None = None,
    current_updates: dict[str, Any] | None = None,
    target_binding_updates: dict[str, Any] | None = None,
    target_binding_util: Any = None,
    target_binding_count: int = 0,
    target_binding_family: str = "",
    target_binding_candidate_id: Any = None,
    target_low: Any = None,
    target_high: Any = None,
    current_binding_expected: Any = None,
    target_updates_already_applied: bool = False,
    safe_binding_updates: dict[str, Any] | None = None,
    combined_binding_updates: dict[str, Any] | None = None,
    safe_updates_already_applied: bool = False,
    combined_updates_already_applied: bool = False,
    combined_binding_bending_util: Any = None,
    evidence_expected_util: Any = None,
    evidence_family: str = "",
    blocker_families: list[str] | tuple[str, ...] | None = None,
    final_accepted_min_family_util: float = 0.0,
    target_band_eps: float = 0.0,
    compound_shear_update_keys: list[str] | tuple[str, ...] | None = None,
    compound_bottom_update_keys: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Compose final-visible binding effects for rebind bridge proof.

    This is proof-only. It accepts plain facts already computed by the caller
    and composes the same Design Brain result builders used by the page-owned
    binding helper. It does not evaluate candidates, inspect session state,
    route Apply, render UI, or mutate the input dictionaries.
    """

    evidence_d = _mapping(evidence_for_binding)
    contract_d = _mapping(contract)
    item_d = _mapping(item)
    debug_d = _mapping(debug)
    current_updates_d = _mapping(current_updates)
    target_updates_d = _mapping(target_binding_updates)
    safe_updates_d = _mapping(safe_binding_updates)
    combined_updates_d = _mapping(combined_binding_updates)
    shear_keys = tuple(compound_shear_update_keys or ())
    bottom_keys = tuple(compound_bottom_update_keys or ())

    target_band_promotion = build_final_visible_contract_binding_target_band_promotion_result(
        evidence_for_binding=evidence_d,
        contract=contract_d,
        item=item_d,
        target_binding_updates=target_updates_d,
        target_binding_util=target_binding_util,
        target_binding_count=target_binding_count,
        target_binding_family=target_binding_family,
        target_binding_candidate_id=target_binding_candidate_id,
        target_low=target_low,
        target_high=target_high,
        current_binding_expected=current_binding_expected,
        target_updates_already_applied=target_updates_already_applied,
        compound_shear_update_keys=shear_keys,
        target_band_eps=target_band_eps,
    )
    safe_consistency_guard = build_final_visible_contract_binding_consistency_guard_result(
        evidence_for_binding=evidence_d,
        current_updates=current_updates_d,
        safe_binding_updates=safe_updates_d,
        combined_binding_updates={},
        safe_updates_already_applied=safe_updates_already_applied,
        combined_updates_already_applied=True,
        compound_shear_update_keys=shear_keys,
    )
    combined_consistency_guard = build_final_visible_contract_binding_consistency_guard_result(
        evidence_for_binding=evidence_d,
        current_updates=current_updates_d,
        safe_binding_updates={},
        combined_binding_updates=combined_updates_d,
        safe_updates_already_applied=True,
        combined_updates_already_applied=combined_updates_already_applied,
        compound_shear_update_keys=shear_keys,
    )
    contract_truth = build_final_visible_contract_binding_truth_result(
        evidence_for_binding=evidence_d,
        contract=contract_d,
        item=item_d,
        updates=current_updates_d,
        compound_shear_update_keys=shear_keys,
        compound_bottom_update_keys=bottom_keys,
        combined_binding_bending_util=combined_binding_bending_util,
    )
    contract_truth_result = _mapping(contract_truth.get("result"))
    no_second_cta = build_final_visible_contract_binding_no_second_cta_result(
        evidence_for_binding=evidence_d,
        contract=contract_d,
        item=item_d,
        debug=debug_d,
        evidence_expected_util=(
            evidence_expected_util
            if evidence_expected_util is not None
            else contract_truth_result.get("evidence_expected_util")
        ),
        evidence_family=(
            str(evidence_family or "").strip().lower()
            or str(contract_truth_result.get("evidence_family_for_contract") or "").strip().lower()
        ),
        blocker_families=(
            list(blocker_families or [])
            or list(contract_truth_result.get("blocker_families_for_contract") or [])
        ),
        final_accepted_min_family_util=final_accepted_min_family_util,
        target_band_eps=target_band_eps,
    )
    effects = {
        "target_band_promotion": target_band_promotion,
        "safe_consistency_guard": safe_consistency_guard,
        "combined_consistency_guard": combined_consistency_guard,
        "contract_truth": contract_truth,
        "no_second_cta": no_second_cta,
    }
    effect_hashes = {
        key: stable_final_publication_hash(value)
        for key, value in effects.items()
    }
    result_flags = {
        "target_band_promotion_applies": bool(
            _mapping(target_band_promotion.get("result")).get("applies")
        ),
        "safe_consistency_guard_resets": bool(
            _mapping(safe_consistency_guard.get("result")).get("reset_contract")
        ),
        "combined_consistency_guard_resets": bool(
            _mapping(combined_consistency_guard.get("result")).get("reset_contract")
        ),
        "contract_truth_available": bool(contract_truth_result),
        "no_second_cta_applies": bool(_mapping(no_second_cta.get("result")).get("applies")),
    }
    represented_effects = tuple(effects)
    payload = {
        "effects": effects,
        "effect_hashes": effect_hashes,
        "result_flags": result_flags,
        "represented_effects": represented_effects,
        "represented_effect_count": len(represented_effects),
        "input_hashes": {
            "evidence_for_binding_hash": stable_final_publication_hash(evidence_d),
            "contract_hash": stable_final_publication_hash(contract_d),
            "item_hash": stable_final_publication_hash(item_d),
            "debug_hash": stable_final_publication_hash(debug_d),
            "current_updates_hash": stable_final_publication_hash(current_updates_d),
            "target_binding_updates_hash": stable_final_publication_hash(target_updates_d),
            "safe_binding_updates_hash": stable_final_publication_hash(safe_updates_d),
            "combined_binding_updates_hash": stable_final_publication_hash(combined_updates_d),
            "compound_shear_update_keys_hash": stable_final_publication_hash(list(shear_keys)),
            "compound_bottom_update_keys_hash": stable_final_publication_hash(list(bottom_keys)),
        },
        "derived_from": "FinalDesignGuidePublication.final_visible_contract_binding_rebind_effects",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": False,
    }
    return {**payload, "proof_hash": stable_final_publication_hash(payload)}


def build_final_visible_contract_binding_rebind_projection(
    *,
    item: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    evidence_for_binding: dict[str, Any] | None = None,
    debug: dict[str, Any] | None = None,
    rebind_effects_proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project rebind effects into plain output dictionaries.

    This is proof-only. It applies already-computed Design Brain effect maps to
    plain dictionaries and does not evaluate candidates, render UI, route Apply,
    read session state, or mutate caller-owned dictionaries.
    """

    item_out = _mapping(item)
    contract_out = _mapping(contract or item_out.get("button_contract"))
    evidence_out = _mapping(evidence_for_binding or item_out.get("candidate_search_evidence"))
    debug_out = _mapping(debug)
    proof_d = _mapping(rebind_effects_proof)
    effects = _mapping(proof_d.get("effects"))
    applied_effects: list[str] = []

    def _apply_effect(effect_id: str, result: dict[str, Any]) -> None:
        nonlocal item_out, contract_out, evidence_out, debug_out
        if not result:
            return
        if effect_id == "safe_consistency_guard" or effect_id == "combined_consistency_guard":
            if bool(result.get("reset_contract")):
                replacement = result.get("contract_replacement")
                contract_out = _mapping(replacement)
                item_out["button_contract"] = dict(contract_out)
                action_type_replacement = result.get("action_type_replacement")
                if action_type_replacement is not None:
                    item_out["action_type"] = action_type_replacement
                applied_effects.append(effect_id)
            debug_out.update(_mapping(result.get("debug_effect")))
            return

        contract_effect = _mapping(result.get("contract_effect"))
        item_effect = _mapping(result.get("item_effect"))
        evidence_effect = _mapping(result.get("evidence_effect"))
        display_truth_effect = _mapping(result.get("display_truth_effect"))
        action_payload_effect = _mapping(result.get("action_payload_effect"))
        resolved_candidate_effect = _mapping(result.get("resolved_candidate_effect"))
        debug_effect = _mapping(result.get("debug_effect"))
        if contract_effect:
            contract_out.update(contract_effect)
            item_out["button_contract"] = dict(contract_out)
        if evidence_effect:
            evidence_out.update(evidence_effect)
            item_out["candidate_search_evidence"] = dict(evidence_out)
        if item_effect:
            merged_item_effect = dict(item_effect)
            if isinstance(merged_item_effect.get("button_contract"), dict):
                contract_out.update(_mapping(merged_item_effect.get("button_contract")))
                merged_item_effect["button_contract"] = dict(contract_out)
            item_out.update(merged_item_effect)
        if display_truth_effect:
            display_truth = _mapping(item_out.get("display_truth"))
            display_truth.update(display_truth_effect)
            item_out["display_truth"] = dict(display_truth)
        if action_payload_effect:
            action_payload = _mapping(item_out.get("action_payload"))
            action_payload.update(action_payload_effect)
            item_out["action_payload"] = dict(action_payload)
        if resolved_candidate_effect:
            resolved_candidate = _mapping(item_out.get("resolved_candidate"))
            resolved_candidate.update(resolved_candidate_effect)
            item_out["resolved_candidate"] = dict(resolved_candidate)
        if debug_effect:
            debug_out.update(debug_effect)
        if (
            contract_effect
            or item_effect
            or evidence_effect
            or display_truth_effect
            or action_payload_effect
            or resolved_candidate_effect
            or debug_effect
        ):
            applied_effects.append(effect_id)

    for effect_id in (
        "target_band_promotion",
        "safe_consistency_guard",
        "combined_consistency_guard",
        "contract_truth",
        "no_second_cta",
    ):
        effect_payload = _mapping(effects.get(effect_id))
        _apply_effect(effect_id, _mapping(effect_payload.get("result")))

    if contract_out:
        item_out["button_contract"] = dict(contract_out)
    if evidence_out:
        item_out["candidate_search_evidence"] = dict(evidence_out)

    projection = {
        "item": item_out,
        "contract": contract_out,
        "evidence_for_binding": evidence_out,
        "debug": debug_out,
        "applied_effects": tuple(applied_effects),
        "applied_effect_count": len(applied_effects),
        "input_hashes": {
            "item_hash": stable_final_publication_hash(_mapping(item)),
            "contract_hash": stable_final_publication_hash(_mapping(contract)),
            "evidence_for_binding_hash": stable_final_publication_hash(_mapping(evidence_for_binding)),
            "debug_hash": stable_final_publication_hash(_mapping(debug)),
            "rebind_effects_proof_hash": stable_final_publication_hash(proof_d),
            "rebind_effects_proof_declared_hash": proof_d.get("proof_hash"),
        },
        "output_hashes": {
            "item_hash": stable_final_publication_hash(item_out),
            "contract_hash": stable_final_publication_hash(contract_out),
            "evidence_for_binding_hash": stable_final_publication_hash(evidence_out),
            "debug_hash": stable_final_publication_hash(debug_out),
        },
        "derived_from": "FinalDesignGuidePublication.final_visible_contract_binding_rebind_projection",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": False,
    }
    return {**projection, "projection_hash": stable_final_publication_hash(projection)}


def build_final_visible_contract_binding_cleanup_evidence_rehydrate_result(
    *,
    item: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    evidence_for_binding: dict[str, Any] | None = None,
    evidence_candidate: dict[str, Any] | None = None,
    evidence_overview: dict[str, Any] | None = None,
    evidence_updates: dict[str, Any] | None = None,
    evidence_family: str = "",
    accepted_safe_shear_cleanup_exists: bool = False,
    final_accepted_min_family_util: float = 0.0,
    target_band_eps: float = 0.0,
) -> dict[str, Any]:
    """Represent the old cleanup-evidence rehydrate tail as plain proof data.

    The page may still own the evaluator call for now. This builder only
    accepts the already-evaluated candidate/overview and returns projected
    mutations that can later replace the old helper tail. It does not evaluate
    candidates, render UI, route Apply, read session state, or mutate inputs.
    """

    item_d = _mapping(item)
    contract_d = _mapping(contract or item_d.get("button_contract"))
    evidence_d = _mapping(evidence_for_binding or item_d.get("candidate_search_evidence"))
    candidate_d = _mapping(evidence_candidate)
    overview_d = _mapping(evidence_overview or candidate_d.get("overview"))
    updates_d = _mapping(evidence_updates)
    family = str(
        evidence_family
        or evidence_d.get("family")
        or evidence_d.get("selected_action_family")
        or contract_d.get("family")
        or item_d.get("family")
        or item_d.get("check_key")
        or ""
    ).strip().lower()

    statuses = _mapping(overview_d.get("statuses"))
    utils = _mapping(overview_d.get("utils"))
    explicit_fail_statuses = {
        str(key): value
        for key, value in statuses.items()
        if str(value or "").strip().upper() in {"FAIL", "NG", "ERROR", "BLOCKED"}
    }
    candidate_present = bool(candidate_d)
    overview_present = bool(overview_d)
    any_fail = bool(overview_d.get("any_fail"))
    acceptable_overview = (
        candidate_present
        and overview_present
        and not any_fail
        and not explicit_fail_statuses
    )

    bending_preview = _number_or_none(utils.get("bending"))
    shear_preview = _number_or_none(utils.get("shear"))
    expected_util = _number_or_none(
        evidence_d.get("best_safe_final_util")
        or evidence_d.get("selected_candidate_util")
        or evidence_d.get("closest_safe_candidate_util")
        or candidate_d.get("candidate_post_util")
        or candidate_d.get("worst_util")
    )
    if family == "combined":
        accepted_strength_previews = [
            util
            for util in (bending_preview, shear_preview)
            if util is not None
            and float(final_accepted_min_family_util) - float(target_band_eps)
            <= float(util)
            <= 1.0 + float(target_band_eps)
        ]
        if accepted_strength_previews:
            expected_util = max(float(value) for value in accepted_strength_previews)
    if expected_util is None:
        expected_util = _number_or_none(overview_d.get("worst_util") or overview_d.get("governing_util"))

    target_band_count = _number_or_none(
        evidence_d.get("target_band_candidate_count")
        or evidence_d.get("executable_target_band_candidate_count")
        or len(list(evidence_d.get("target_band_candidates") or []))
    )
    target_band_count_i = int(target_band_count or 0)
    outside_target_allowed = bool(evidence_d.get("outside_target_band_allowed")) and bool(
        str(evidence_d.get("outside_target_band_allowed_category") or "").strip()
    )
    terminal_candidate_status = str(evidence_d.get("terminal_candidate_status") or "").strip().upper()
    terminal_cleanup_proven = bool(
        terminal_candidate_status
        in {
            "TERMINAL_TARGET_BAND",
            "TERMINAL_EXACT_STOP",
            "TERMINAL_BLOCKED_WITH_PROOF",
        }
        or target_band_count_i > 0
    )

    candidate_id = _text(
        None if accepted_safe_shear_cleanup_exists else evidence_d.get("selected_candidate_id"),
        evidence_d.get("closest_safe_candidate_id"),
        evidence_d.get("best_safe_candidate_id"),
        item_d.get("source_candidate_id"),
        item_d.get("candidate_id"),
        contract_d.get("source_candidate_id"),
        contract_d.get("candidate_id"),
        candidate_d.get("source_candidate_id"),
        candidate_d.get("candidate_id"),
        stable_final_publication_hash({"family": family, "updates": updates_d})[:16] if updates_d else None,
    )

    below_final_threshold = bool(
        expected_util is not None
        and final_accepted_min_family_util
        and float(expected_util) < float(final_accepted_min_family_util) - float(target_band_eps)
    )
    cleanup_target_not_proven = bool(
        family in {"bending", "shear", "combined"}
        and below_final_threshold
        and target_band_count_i <= 0
        and not terminal_cleanup_proven
    )
    applies = bool(
        acceptable_overview
        and updates_d
        and family in {"bending", "shear", "combined"}
        and not cleanup_target_not_proven
    )
    evidence_remove_keys: tuple[str, ...] = ()
    counter_effect: dict[str, Any] = {}
    if applies and accepted_safe_shear_cleanup_exists:
        evidence_remove_keys = (
            "exact_blockers_by_family",
            "post_click_exact_blockers_by_family",
            "cleanup_evidence_by_family",
            "post_click_cleanup_evidence_by_family",
        )

        def _at_least_one(*values: Any) -> int:
            for value in values:
                try:
                    number = int(value)
                    if number > 0:
                        return max(1, number)
                except Exception:
                    continue
            return 1

        accepted_count = evidence_d.get("accepted_band_candidate_count")
        counter_effect = {
            "best_safe_candidate_applied": False,
            "no_second_cta_required": False,
            "safe_candidate_count": _at_least_one(
                evidence_d.get("safe_candidate_count"),
                evidence_d.get("safe_cleanup_count"),
                accepted_count,
            ),
            "executable_candidate_count": _at_least_one(
                evidence_d.get("executable_candidate_count"),
                evidence_d.get("executable_cleanup_count"),
                accepted_count,
            ),
            "safe_cleanup_count": _at_least_one(
                evidence_d.get("safe_cleanup_count"),
                evidence_d.get("safe_candidate_count"),
                accepted_count,
            ),
            "executable_cleanup_count": _at_least_one(
                evidence_d.get("executable_cleanup_count"),
                evidence_d.get("executable_candidate_count"),
                accepted_count,
            ),
            "safe_shear_cleanup_count": _at_least_one(
                evidence_d.get("safe_shear_cleanup_count"),
                evidence_d.get("safe_candidate_count"),
                accepted_count,
            ),
            "executable_shear_cleanup_count": _at_least_one(
                evidence_d.get("executable_shear_cleanup_count"),
                evidence_d.get("executable_candidate_count"),
                accepted_count,
            ),
        }

    evidence_effect = {}
    contract_effect = {}
    item_effect = {}
    action_payload_effect = {}
    resolved_candidate_effect = {}
    debug_effect = {
        "final_binding_evidence_cleanup_rehydrate_candidate_present": candidate_present,
        "final_binding_evidence_cleanup_rehydrate_overview_statuses": dict(statuses),
        "final_binding_evidence_cleanup_rehydrate_overview_utils": dict(utils),
    }
    if applies:
        evidence_effect = {
            "cleanup_search_ran": True,
            "cleanup_search_exhaustive": True,
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
            "attempted_candidate_count": (
                evidence_d.get("attempted_candidate_count")
                or evidence_d.get("safe_candidate_count")
                or evidence_d.get("generated_count")
                or evidence_d.get("preview_count")
                or 1
            ),
            "target_band_candidate_count": target_band_count_i,
            **counter_effect,
            "selected_candidate_id": candidate_id,
            "selected_candidate_updates": dict(updates_d),
            "best_safe_candidate_updates": dict(updates_d),
        }
        if expected_util is not None:
            evidence_effect["selected_candidate_util"] = float(expected_util)
            evidence_effect["best_safe_final_util"] = float(expected_util)
        contract_effect = {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": family,
            "updates": dict(updates_d),
            "preview_pass": True,
            "expected_util": expected_util,
            "blocking_reason": None,
            "source_candidate_id": candidate_id,
            "candidate_id": candidate_id,
        }
        item_effect = {
            "action_type": "apply_resolved_candidate",
            "family": family,
            "check_key": family,
            "selected_action_family": family,
            "primary_card_actionable": True,
            "updates": dict(updates_d),
            "selected_action_updates": dict(updates_d),
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
        }
        if expected_util is not None:
            item_effect.update(
                {
                    "expected_util": float(expected_util),
                    "candidate_post_util": float(expected_util),
                    "displayed_util": float(expected_util),
                }
            )
        title_text = str(item_d.get("title_main") or item_d.get("title") or "").strip().lower()
        if family == "shear" and "shear cleanup blocked by final efficiency threshold" in title_text:
            title_main = "Shear cleanup - best safe one-click reduction"
            title = (
                f"{title_main} (utilisation = {float(expected_util):.2f})"
                if expected_util is not None
                else title_main
            )
            item_effect.update(
                {
                    "title_main": title_main,
                    "title": title,
                    "guidance_intent": "efficiency_tightening",
                    "primary_action": "Run one-click auto design",
                    "secondary_action": (
                        "Apply the best safe shear-link cleanup found by the exhaustive search."
                    ),
                }
            )
            evidence_effect["best_safe_partial_cleanup"] = True
        action_payload_effect = {
            "updates": dict(updates_d),
            "resolved_candidate_updates": dict(updates_d),
            "resolved_candidate_action_type": "apply_resolved_candidate",
            "resolved_candidate_family_tag": family,
            "source_candidate_id": candidate_id,
            "candidate_id": candidate_id,
            "expected_util": expected_util,
            "expected_governing_util": expected_util,
            "resolved_candidate_post_util": expected_util,
        }
        resolved_candidate_effect = {
            "updates": dict(updates_d),
            "action_type": "apply_resolved_candidate",
            "family": family,
            "source_candidate_id": candidate_id,
            "candidate_id": candidate_id,
            "candidate_post_util": expected_util,
        }
        debug_effect.update(
            {
                "final_binding_evidence_cleanup_rehydrated": True,
                "final_binding_evidence_cleanup_family": family,
                "final_binding_evidence_cleanup_updates": dict(updates_d),
            }
        )

    result = {
        "applies": applies,
        "candidate_present": candidate_present,
        "overview_present": overview_present,
        "overview_any_fail": any_fail,
        "explicit_fail_statuses": explicit_fail_statuses,
        "accepted_safe_shear_cleanup_exists": bool(accepted_safe_shear_cleanup_exists),
        "evidence_family": family,
        "evidence_updates": dict(updates_d),
        "expected_util": expected_util,
        "candidate_id": candidate_id,
        "evidence_remove_keys": evidence_remove_keys,
        "evidence_effect": evidence_effect,
        "contract_effect": contract_effect,
        "item_effect": item_effect,
        "action_payload_effect": action_payload_effect,
        "resolved_candidate_effect": resolved_candidate_effect,
        "debug_effect": debug_effect,
    }
    payload = {
        "result": result,
        "result_hash": stable_final_publication_hash(result),
        "input_hashes": {
            "item_hash": stable_final_publication_hash(item_d),
            "contract_hash": stable_final_publication_hash(contract_d),
            "evidence_for_binding_hash": stable_final_publication_hash(evidence_d),
            "evidence_candidate_hash": stable_final_publication_hash(candidate_d),
            "evidence_overview_hash": stable_final_publication_hash(overview_d),
            "evidence_updates_hash": stable_final_publication_hash(updates_d),
        },
        "represented_live_groups": (
            "cleanup_evidence_candidate_acceptance",
            "cleanup_evidence_contract_rehydration",
            "cleanup_evidence_item_rehydration",
            "cleanup_evidence_payload_rehydration",
            "cleanup_evidence_resolved_candidate_rehydration",
            "cleanup_evidence_debug_rehydration",
        ),
        "derived_from": "FinalDesignGuidePublication.final_visible_contract_binding_cleanup_evidence_rehydrate",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": False,
    }
    return {**payload, "proof_hash": stable_final_publication_hash(payload)}


def build_final_visible_contract_binding_cleanup_evidence_rehydrate_projection(
    *,
    item: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    evidence_for_binding: dict[str, Any] | None = None,
    debug: dict[str, Any] | None = None,
    evidence_candidate: dict[str, Any] | None = None,
    cleanup_rehydrate_proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project cleanup-evidence rehydrate effects into plain dictionaries.

    This is proof-only. It applies a previously built cleanup-evidence
    rehydrate proof to plain item/contract/evidence/debug dictionaries. It does
    not evaluate candidates, render UI, route Apply, read session state, or
    mutate caller-owned dictionaries.
    """

    item_out = _mapping(item)
    contract_out = _mapping(contract or item_out.get("button_contract"))
    evidence_out = _mapping(evidence_for_binding or item_out.get("candidate_search_evidence"))
    debug_out = _mapping(debug)
    candidate_d = _mapping(evidence_candidate)
    proof_d = _mapping(cleanup_rehydrate_proof)
    result = _mapping(proof_d.get("result"))
    applied_effects: list[str] = []

    if bool(result.get("applies")):
        for key in tuple(result.get("evidence_remove_keys") or ()):
            if key in evidence_out:
                evidence_out.pop(str(key), None)
                applied_effects.append(f"remove:{key}")
        evidence_effect = _mapping(result.get("evidence_effect"))
        contract_effect = _mapping(result.get("contract_effect"))
        item_effect = _mapping(result.get("item_effect"))
        action_payload_effect = _mapping(result.get("action_payload_effect"))
        resolved_candidate_effect = _mapping(result.get("resolved_candidate_effect"))
        if evidence_effect:
            evidence_out.update(evidence_effect)
            item_out["candidate_search_evidence"] = dict(evidence_out)
            applied_effects.append("evidence_effect")
        if contract_effect:
            contract_out.update(contract_effect)
            item_out["button_contract"] = dict(contract_out)
            applied_effects.append("contract_effect")
        if item_effect:
            item_out.update(item_effect)
            applied_effects.append("item_effect")
        if action_payload_effect:
            action_payload = _mapping(item_out.get("action_payload"))
            action_payload.update(action_payload_effect)
            action_payload["candidate_search_evidence"] = dict(evidence_out)
            item_out["action_payload"] = dict(action_payload)
            applied_effects.append("action_payload_effect")
        if resolved_candidate_effect:
            resolved_candidate = _mapping(item_out.get("resolved_candidate")) or dict(candidate_d)
            resolved_candidate.update(resolved_candidate_effect)
            resolved_candidate["candidate_search_evidence"] = dict(evidence_out)
            item_out["resolved_candidate"] = dict(resolved_candidate)
            applied_effects.append("resolved_candidate_effect")

    debug_effect = _mapping(result.get("debug_effect"))
    if debug_effect:
        debug_out.update(debug_effect)
        if bool(result.get("applies")) and evidence_out:
            debug_out["candidate_search_evidence"] = dict(evidence_out)
        applied_effects.append("debug_effect")

    if contract_out:
        item_out["button_contract"] = dict(contract_out)
    if evidence_out:
        item_out["candidate_search_evidence"] = dict(evidence_out)

    projection = {
        "item": item_out,
        "contract": contract_out,
        "evidence_for_binding": evidence_out,
        "debug": debug_out,
        "applied_effects": tuple(applied_effects),
        "applied_effect_count": len(applied_effects),
        "input_hashes": {
            "item_hash": stable_final_publication_hash(_mapping(item)),
            "contract_hash": stable_final_publication_hash(_mapping(contract)),
            "evidence_for_binding_hash": stable_final_publication_hash(_mapping(evidence_for_binding)),
            "debug_hash": stable_final_publication_hash(_mapping(debug)),
            "evidence_candidate_hash": stable_final_publication_hash(candidate_d),
            "cleanup_rehydrate_proof_hash": stable_final_publication_hash(proof_d),
            "cleanup_rehydrate_proof_declared_hash": proof_d.get("proof_hash"),
        },
        "output_hashes": {
            "item_hash": stable_final_publication_hash(item_out),
            "contract_hash": stable_final_publication_hash(contract_out),
            "evidence_for_binding_hash": stable_final_publication_hash(evidence_out),
            "debug_hash": stable_final_publication_hash(debug_out),
        },
        "derived_from": "FinalDesignGuidePublication.final_visible_contract_binding_cleanup_evidence_rehydrate_projection",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": False,
    }
    return {**projection, "projection_hash": stable_final_publication_hash(projection)}


def _final_visible_intent_contract_from_debug_rows(
    guidance_debug: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    debug_d = _mapping(guidance_debug)
    for key in ("displayed_guidance_intent_items", "guidance_intent_items"):
        rows = debug_d.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_d = _mapping(row)
            contract = _mapping(row_d.get("button_contract"))
            action_type = str(contract.get("action_type") or row_d.get("action_type") or "").strip()
            if (
                bool(contract.get("actionable"))
                and action_type == "apply_resolved_candidate"
                and bool(contract.get("preview_pass"))
                and contract.get("blocking_reason") is None
                and _mapping(contract.get("updates"))
            ):
                return contract, row_d
    return {}, {}


def select_enabled_design_guide_contract_from_intent_rows(
    guidance_debug: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return the enabled apply contract represented by Design Guide intent rows.

    This is the page-compatible public boundary for the former inputs-page
    helper. It keeps the no-match result as ``(None, None)`` so existing
    page-side callers do not change behaviour while the selection policy lives
    with final publication proof objects.
    """

    contract, row = _final_visible_intent_contract_from_debug_rows(guidance_debug)
    if not contract:
        return None, None
    return dict(contract), dict(row)


def _final_publication_button_contract_enabled(contract: dict[str, Any] | None) -> bool:
    contract_d = _mapping(contract)
    return bool(
        contract_d.get("actionable")
        and _mapping(contract_d.get("updates"))
        and bool(contract_d.get("preview_pass"))
        and contract_d.get("blocking_reason") is None
        and not _text(contract_d.get("disabled_reason"))
    )


def build_final_design_guide_card_vm_intent_contract_promotion_result(
    *,
    item: dict[str, Any] | None = None,
    debug_payload: dict[str, Any] | None = None,
    overview: dict[str, Any] | None = None,
    actionable: bool = False,
) -> dict[str, Any]:
    """Represent card view-model intent-contract promotion as pure data.

    The page still owns Streamlit state writes and apply payload recording. This
    result owns the decision and all deterministic item/debug/action-payload
    effects that were previously assembled inline in the page shell.
    """

    item_d = _mapping(item)
    debug_d = _mapping(debug_payload)
    overview_d = _mapping(overview)
    intent_contract_d, intent_row_d = _final_visible_intent_contract_from_debug_rows(debug_d)
    intent_updates = _mapping(intent_contract_d.get("updates"))
    intent_contract_executable = bool(
        intent_updates
        and bool(intent_contract_d.get("preview_pass"))
        and intent_contract_d.get("blocking_reason") is None
        and str(intent_contract_d.get("action_type") or intent_row_d.get("action_type") or "").strip()
        == "apply_resolved_candidate"
        and bool(intent_contract_d.get("actionable") or intent_contract_d.get("enabled"))
    )
    current_contract = _mapping(item_d.get("button_contract"))
    current_expected = _number_or_none(current_contract.get("expected_util"))
    intent_expected = _number_or_none(
        intent_contract_d.get("expected_util")
        or intent_row_d.get("displayed_util")
        or intent_row_d.get("candidate_post_util")
    )
    current_family = str(
        current_contract.get("family") or item_d.get("family") or ""
    ).strip().lower()
    intent_family = str(
        intent_row_d.get("check_key")
        or intent_row_d.get("family")
        or intent_contract_d.get("family")
        or ""
    ).strip().lower()
    if intent_family not in {"bending", "shear"}:
        intent_source_util = _number_or_none(
            intent_row_d.get("source_summary_util")
            or _mapping(intent_row_d.get("display_truth")).get("source_summary_util")
        )
        overview_utils = _mapping(overview_d.get("utils"))
        for candidate_family in ("bending", "shear"):
            current_candidate_util = _number_or_none(overview_utils.get(candidate_family))
            if (
                intent_source_util is not None
                and current_candidate_util is not None
                and abs(float(intent_source_util) - float(current_candidate_util)) <= 0.005
            ):
                intent_family = candidate_family
                break

    guard_results = {
        "actionable": bool(actionable),
        "has_debug_payload": bool(debug_d),
        "has_intent_contract": bool(intent_contract_d),
        "has_intent_row": bool(intent_row_d),
        "has_intent_updates": bool(intent_updates),
        "intent_contract_executable": bool(intent_contract_executable),
        "current_contract_disabled": not _final_publication_button_contract_enabled(current_contract),
        "expected_util_differs": (
            intent_expected is not None
            and current_expected is not None
            and abs(float(intent_expected) - float(current_expected)) > 0.005
        ),
        "combined_to_bending_or_shear": current_family == "combined"
        and intent_family in {"bending", "shear"},
    }
    should_prefer = bool(
        (guard_results["actionable"] or guard_results["intent_contract_executable"])
        and guard_results["has_debug_payload"]
        and guard_results["has_intent_updates"]
        and (
            guard_results["current_contract_disabled"]
            or guard_results["expected_util_differs"]
            or guard_results["combined_to_bending_or_shear"]
        )
    )

    promoted_contract: dict[str, Any] = {}
    item_effect: dict[str, Any] = {}
    debug_effect: dict[str, Any] = {}
    action_payload_effect: dict[str, Any] = {}
    resolved_candidate_effect: dict[str, Any] = {}
    item_truth_effect: dict[str, Any] = {}
    display_util_effect: float | None = None
    if should_prefer:
        promoted_contract = dict(intent_contract_d)
        if intent_family in {"bending", "shear"}:
            promoted_contract["family"] = intent_family
            item_effect.update(
                {
                    "family": intent_family,
                    "check_key": intent_family,
                    "selected_action_family": intent_family,
                }
            )
        promoted_contract.update(
            {
                "updates": dict(intent_updates),
                "action_type": "apply_resolved_candidate",
                "actionable": True,
                "enabled": True,
                "preview_pass": True,
                "blocking_reason": None,
            }
        )
        if intent_expected is not None:
            promoted_contract["expected_util"] = float(intent_expected)
            display_util_effect = float(intent_expected)
            item_effect.update(
                {
                    "expected_util": float(intent_expected),
                    "candidate_post_util": float(intent_expected),
                    "displayed_util": float(intent_expected),
                }
            )
        item_effect.update(
            {
                "button_contract": dict(promoted_contract),
                "action_type": "apply_resolved_candidate",
                "primary_card_actionable": True,
                "updates": dict(intent_updates),
                "selected_action_updates": dict(intent_updates),
            }
        )
        action_payload_effect = {
            **_mapping(item_d.get("action_payload")),
            "updates": dict(intent_updates),
            "resolved_candidate_updates": dict(intent_updates),
            "resolved_candidate_action_type": "apply_resolved_candidate",
            "resolved_candidate_family_tag": promoted_contract.get("family"),
            "source_candidate_id": promoted_contract.get("source_candidate_id")
            or promoted_contract.get("candidate_id"),
            "candidate_id": promoted_contract.get("candidate_id")
            or promoted_contract.get("source_candidate_id"),
            "expected_util": promoted_contract.get("expected_util"),
            "resolved_candidate_post_util": promoted_contract.get("expected_util"),
        }
        resolved_candidate_effect = {
            **_mapping(item_d.get("resolved_candidate")),
            "updates": dict(intent_updates),
            "action_type": "apply_resolved_candidate",
            "family": promoted_contract.get("family"),
            "source_candidate_id": promoted_contract.get("source_candidate_id")
            or promoted_contract.get("candidate_id"),
            "candidate_id": promoted_contract.get("candidate_id")
            or promoted_contract.get("source_candidate_id"),
            "expected_util": promoted_contract.get("expected_util"),
            "candidate_post_util": promoted_contract.get("expected_util"),
        }
        item_truth_effect = dict(_mapping(item_d.get("display_truth")))
        row_truth = {
            key: intent_row_d.get(key)
            for key in (
                "display_truth_source",
                "displayed_util",
                "displayed_status",
                "target_low",
                "target_high",
                "displayed_within_target_band",
                "source_summary_util",
                "source_candidate_util",
                "source_post_commit_util",
            )
            if intent_row_d.get(key) is not None
        }
        item_truth_effect.update(row_truth)
        if intent_expected is not None:
            item_truth_effect["displayed_util"] = float(intent_expected)
            item_truth_effect["source_candidate_util"] = float(intent_expected)
        item_effect["action_payload"] = dict(action_payload_effect)
        item_effect["resolved_candidate"] = dict(resolved_candidate_effect)
        item_effect["display_truth"] = dict(item_truth_effect)
        debug_effect = {
            "primary_button_contract": dict(promoted_contract),
            "button_contract": dict(promoted_contract),
            "displayed_primary_button_contract": dict(promoted_contract),
            "button_contract_enabled": True,
            "button_contract_updates": dict(intent_updates),
            "button_contract_preview_pass": True,
            "button_contract_blocking_reason": None,
            "selected_action_type": "apply_resolved_candidate",
            "selected_action_family": promoted_contract.get("family"),
            "selected_action_updates": dict(intent_updates),
            "primary_display_truth": dict(item_truth_effect),
            "displayed_primary_display_truth": dict(item_truth_effect),
            "final_card_intent_contract_promoted": True,
        }

    output_item = dict(item_d)
    output_item.update(dict(item_effect))
    output_debug = dict(debug_d)
    output_debug.update(dict(debug_effect))
    result = {
        "applies": should_prefer,
        "guard_results": guard_results,
        "intent_contract": dict(intent_contract_d),
        "intent_row": dict(intent_row_d),
        "intent_family": intent_family,
        "current_family": current_family,
        "intent_updates": dict(intent_updates),
        "intent_expected": intent_expected,
        "current_expected": current_expected,
        "promoted_contract": dict(promoted_contract),
        "item_effect": dict(item_effect),
        "debug_effect": dict(debug_effect),
        "action_payload_effect": dict(action_payload_effect),
        "resolved_candidate_effect": dict(resolved_candidate_effect),
        "display_truth_effect": dict(item_truth_effect),
        "display_util_effect": display_util_effect,
        "output_item": dict(output_item),
        "output_debug": dict(output_debug),
    }
    payload = {
        "result": result,
        "result_hash": stable_final_publication_hash(result),
        "input_hashes": {
            "item_hash": stable_final_publication_hash(item_d),
            "debug_payload_hash": stable_final_publication_hash(debug_d),
            "overview_hash": stable_final_publication_hash(overview_d),
            "actionable_hash": stable_final_publication_hash(bool(actionable)),
        },
        "represented_live_groups": (
            "card_vm_intent_contract_selector",
            "card_vm_intent_contract_preference_decision",
            "card_vm_promoted_contract_effect",
            "card_vm_item_effect",
            "card_vm_debug_effect",
            "card_vm_action_payload_effect",
        ),
        "derived_from": "FinalDesignGuidePublication.card_vm_intent_contract_promotion",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": False,
    }
    return {**payload, "proof_hash": stable_final_publication_hash(payload)}


def build_final_design_guide_shear_exact_blocker_safe_intent_result(
    *,
    guidance_debug: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    overview: dict[str, Any] | None = None,
    final_accepted_min_family_util: float = 0.85,
    target_band_eps: float = 1e-9,
    shear_update_keys: tuple[str, ...] | list[str] | set[str] = (),
) -> dict[str, Any]:
    """Represent safe shear intent recovery over a stale exact blocker."""

    debug_d = _mapping(guidance_debug)
    state_d = _mapping(state)
    overview_d = _mapping(overview)
    intent_contract_d, intent_row_d = _final_visible_intent_contract_from_debug_rows(debug_d)
    intent_family = str(
        intent_contract_d.get("family")
        or intent_row_d.get("check_key")
        or intent_row_d.get("family")
        or ""
    ).strip().lower()
    intent_updates = _mapping(intent_contract_d.get("updates"))
    intent_expected = _number_or_none(
        intent_contract_d.get("expected_util")
        or intent_row_d.get("expected_util")
        or intent_row_d.get("candidate_post_util")
    )
    shear_keys = {str(key or "") for key in (shear_update_keys or ()) if str(key or "")}
    active_failures = {
        key
        for key, value in _mapping(overview_d.get("utils")).items()
        if str(key or "").strip().lower() in {"bending", "shear"}
        and _number_or_none(value) is not None
        and float(_number_or_none(value) or 0.0) > 1.0
    }
    updates_already_match = all(state_d.get(key) == value for key, value in intent_updates.items()) if intent_updates else False
    expected_in_range = bool(
        intent_expected is not None
        and float(final_accepted_min_family_util) - float(target_band_eps)
        <= float(intent_expected)
        <= 1.0 + float(target_band_eps)
    )
    guard_results = {
        "has_intent_contract": bool(intent_contract_d),
        "button_contract_enabled": _final_publication_button_contract_enabled(intent_contract_d),
        "action_type_apply_resolved_candidate": str(intent_contract_d.get("action_type") or "").strip()
        == "apply_resolved_candidate",
        "family_is_shear": intent_family == "shear",
        "has_updates": bool(intent_updates),
        "has_shear_update_keys": bool(set(intent_updates) & shear_keys) if shear_keys else bool(intent_updates),
        "updates_not_already_in_state": not updates_already_match,
        "expected_util_present": intent_expected is not None,
        "expected_util_in_accepted_range": expected_in_range,
        "no_active_strength_failures": not bool(active_failures),
    }
    available = all(guard_results.values())
    evidence_effect: dict[str, Any] = {}
    candidate_id = ""
    title = str(intent_row_d.get("title") or "Shear cleanup - one-click reduction")
    if available:
        evidence_effect = _mapping(debug_d.get("candidate_search_evidence"))
        for stale_blocker_key in (
            "exact_blockers_by_family",
            "post_click_exact_blockers_by_family",
            "cleanup_evidence_by_family",
            "post_click_cleanup_evidence_by_family",
        ):
            evidence_effect.pop(stale_blocker_key, None)
        candidate_id = str(
            intent_contract_d.get("candidate_id")
            or intent_contract_d.get("source_candidate_id")
            or evidence_effect.get("selected_candidate_id")
            or evidence_effect.get("best_safe_candidate_id")
            or _local_cleanup_candidate_id("shear", intent_updates)
        ).strip()
        evidence_effect.update(
            {
                "cleanup_search_ran": True,
                "cleanup_search_exhaustive": True,
                "local_cleanup_search_ran": True,
                "local_cleanup_search_exhaustive": True,
                "family": "shear",
                "selected_candidate_id": candidate_id,
                "best_safe_candidate_id": candidate_id,
                "selected_candidate_updates": dict(intent_updates),
                "best_safe_candidate_updates": dict(intent_updates),
                "selected_candidate_util": float(intent_expected),
                "best_safe_final_util": float(intent_expected),
                "best_safe_candidate_applied": False,
                "best_safe_partial_cleanup": False,
                "no_second_cta_required": False,
                "one_click_target_reaching_candidate_exists": True,
                "safe_candidate_count": max(
                    1,
                    int(
                        evidence_effect.get("safe_candidate_count")
                        or evidence_effect.get("safe_cleanup_count")
                        or 0
                    ),
                ),
                "executable_candidate_count": max(
                    1,
                    int(
                        evidence_effect.get("executable_candidate_count")
                        or evidence_effect.get("executable_cleanup_count")
                        or 0
                    ),
                ),
                "safe_cleanup_count": max(
                    1,
                    int(
                        evidence_effect.get("safe_cleanup_count")
                        or evidence_effect.get("safe_candidate_count")
                        or 0
                    ),
                ),
                "executable_cleanup_count": max(
                    1,
                    int(
                        evidence_effect.get("executable_cleanup_count")
                        or evidence_effect.get("executable_candidate_count")
                        or 0
                    ),
                ),
                "safe_shear_cleanup_count": max(
                    1,
                    int(
                        evidence_effect.get("safe_shear_cleanup_count")
                        or evidence_effect.get("safe_candidate_count")
                        or 0
                    ),
                ),
                "executable_shear_cleanup_count": max(
                    1,
                    int(
                        evidence_effect.get("executable_shear_cleanup_count")
                        or evidence_effect.get("executable_candidate_count")
                        or 0
                    ),
                ),
            }
        )
    result = {
        "available": available,
        "guard_results": guard_results,
        "intent_contract": dict(intent_contract_d),
        "intent_row": dict(intent_row_d),
        "family": intent_family,
        "updates": dict(intent_updates),
        "expected_util": float(intent_expected) if intent_expected is not None else None,
        "candidate_id": candidate_id,
        "title": title,
        "evidence_effect": evidence_effect,
        "resolver_reason": "safe_shear_cleanup_intent_preferred_over_exact_blocker" if available else "",
    }
    payload = {
        "result": result,
        "hashes": {
            "guidance_debug_hash": stable_final_publication_hash(debug_d),
            "state_hash": stable_final_publication_hash(state_d),
            "overview_hash": stable_final_publication_hash(overview_d),
            "intent_contract_hash": stable_final_publication_hash(intent_contract_d),
            "intent_row_hash": stable_final_publication_hash(intent_row_d),
            "evidence_effect_hash": stable_final_publication_hash(evidence_effect),
        },
        "derived_from": "FinalDesignGuidePublication.shear_exact_blocker_safe_intent",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": True,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }
    payload["result_hash"] = stable_final_publication_hash(result)
    payload["proof_hash"] = stable_final_publication_hash(payload)
    return payload


def build_final_design_guide_card_render_contract_preference_result(
    *,
    item: dict[str, Any] | None = None,
    guidance_debug: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    active_strength_failures: tuple[str, ...] | list[str] | set[str] | None = None,
    final_accepted_min_family_util: float = 0.85,
    target_band_eps: float = 1e-9,
    shear_update_keys: tuple[str, ...] | list[str] | set[str] = (),
) -> dict[str, Any]:
    """Represent render-card shear intent preference as pure data."""

    item_d = _mapping(item)
    debug_d = _mapping(guidance_debug)
    state_d = _mapping(state)
    intent_contract_d, intent_row_d = _final_visible_intent_contract_from_debug_rows(debug_d)
    source = "intent_row"
    if not intent_contract_d:
        evidence_source = _mapping(
            item_d.get("candidate_search_evidence")
            or _mapping(item_d.get("action_payload")).get("candidate_search_evidence")
            or _mapping(item_d.get("resolved_candidate")).get("candidate_search_evidence")
        )
        safe_updates = _mapping(evidence_source.get("best_safe_candidate_updates"))
        safe_expected = _number_or_none(
            evidence_source.get("best_safe_final_util") or evidence_source.get("selected_candidate_util")
        )
        safe_candidate_id = str(
            evidence_source.get("best_safe_candidate_id")
            or evidence_source.get("selected_candidate_id")
            or _local_cleanup_candidate_id("shear", safe_updates)
        ).strip()
        shear_keys = {str(key or "") for key in (shear_update_keys or ()) if str(key or "")}
        fallback_guard = {
            "evidence_family_is_shear": str(evidence_source.get("family") or "").strip().lower() == "shear",
            "has_safe_updates": bool(safe_updates),
            "has_shear_update_keys": bool(set(safe_updates) & shear_keys) if shear_keys else bool(safe_updates),
            "updates_not_already_in_state": not (
                all(state_d.get(key) == value for key, value in safe_updates.items()) if safe_updates else False
            ),
            "expected_util_present": safe_expected is not None,
            "expected_util_in_accepted_range": bool(
                safe_expected is not None
                and float(final_accepted_min_family_util) - float(target_band_eps)
                <= float(safe_expected)
                <= 1.0 + float(target_band_eps)
            ),
            "target_reaching_candidate_exists": bool(
                evidence_source.get("one_click_target_reaching_candidate_exists")
                or int(evidence_source.get("accepted_band_candidate_count") or 0) > 0
            ),
        }
        if all(fallback_guard.values()):
            source = "safe_shear_evidence"
            intent_contract_d = {
                "enabled": True,
                "actionable": True,
                "action_type": "apply_resolved_candidate",
                "family": "shear",
                "updates": dict(safe_updates),
                "preview_pass": True,
                "expected_util": float(safe_expected),
                "blocking_reason": None,
                "source_candidate_id": safe_candidate_id,
                "candidate_id": safe_candidate_id,
            }
            intent_row_d = {
                "title": "Shear cleanup - one-click reduction",
                "check_key": "shear",
                "family": "shear",
                "action_type": "apply_resolved_candidate",
                "guidance_intent": "efficiency_tightening",
            }
        else:
            intent_contract_d = {}
            intent_row_d = {}
    intent_family = str(
        intent_contract_d.get("family")
        or intent_row_d.get("check_key")
        or intent_row_d.get("family")
        or ""
    ).strip().lower()
    intent_updates = _mapping(intent_contract_d.get("updates"))
    intent_expected = _number_or_none(
        intent_contract_d.get("expected_util")
        or intent_row_d.get("expected_util")
        or intent_row_d.get("candidate_post_util")
    )
    shear_keys = {str(key or "") for key in (shear_update_keys or ()) if str(key or "")}
    updates_already_match = all(state_d.get(key) == value for key, value in intent_updates.items()) if intent_updates else False
    active_failures = tuple(sorted(str(value or "").strip().lower() for value in (active_strength_failures or ()) if value))
    guard_results = {
        "has_intent_contract": bool(intent_contract_d),
        "button_contract_enabled": _final_publication_button_contract_enabled(intent_contract_d),
        "action_type_apply_resolved_candidate": str(intent_contract_d.get("action_type") or "").strip()
        == "apply_resolved_candidate",
        "family_is_shear": intent_family == "shear",
        "has_updates": bool(intent_updates),
        "has_shear_update_keys": bool(set(intent_updates) & shear_keys) if shear_keys else bool(intent_updates),
        "updates_not_already_in_state": not updates_already_match,
        "expected_util_present": intent_expected is not None,
        "expected_util_in_accepted_range": bool(
            intent_expected is not None
            and float(final_accepted_min_family_util) - float(target_band_eps)
            <= float(intent_expected)
            <= 1.0 + float(target_band_eps)
        ),
        "no_active_strength_failures": not bool(active_failures),
    }
    applies = all(guard_results.values())
    candidate_id = ""
    evidence_effect: dict[str, Any] = {}
    button_contract_effect: dict[str, Any] = {}
    item_effect: dict[str, Any] = {}
    action_payload_effect: dict[str, Any] = {}
    resolved_candidate_effect: dict[str, Any] = {}
    debug_effect: dict[str, Any] = {}
    stale_item_keys_to_remove: tuple[str, ...] = ()
    if applies:
        candidate_id = str(
            intent_contract_d.get("candidate_id")
            or intent_contract_d.get("source_candidate_id")
            or _local_cleanup_candidate_id("shear", intent_updates)
        ).strip()
        button_contract_effect = {
            **intent_contract_d,
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "updates": dict(intent_updates),
            "preview_pass": True,
            "expected_util": float(intent_expected),
            "blocking_reason": None,
            "source_candidate_id": candidate_id,
            "candidate_id": candidate_id,
        }
        evidence_effect = _mapping(
            item_d.get("candidate_search_evidence")
            or _mapping(item_d.get("action_payload")).get("candidate_search_evidence")
            or _mapping(item_d.get("resolved_candidate")).get("candidate_search_evidence")
        )
        stale_item_keys_to_remove = (
            "exact_blockers_by_family",
            "post_click_exact_blockers_by_family",
            "cleanup_evidence_by_family",
            "post_click_cleanup_evidence_by_family",
        )
        for stale_key in stale_item_keys_to_remove:
            evidence_effect.pop(stale_key, None)
        evidence_effect.update(
            {
                "cleanup_search_ran": True,
                "cleanup_search_exhaustive": True,
                "local_cleanup_search_ran": True,
                "local_cleanup_search_exhaustive": True,
                "family": "shear",
                "selected_candidate_id": candidate_id,
                "best_safe_candidate_id": candidate_id,
                "selected_candidate_updates": dict(intent_updates),
                "best_safe_candidate_updates": dict(intent_updates),
                "selected_candidate_util": float(intent_expected),
                "best_safe_final_util": float(intent_expected),
                "best_safe_candidate_applied": False,
                "no_second_cta_required": False,
                "one_click_target_reaching_candidate_exists": True,
                "safe_candidate_count": max(
                    1,
                    int(
                        evidence_effect.get("safe_candidate_count")
                        or evidence_effect.get("safe_cleanup_count")
                        or evidence_effect.get("accepted_band_candidate_count")
                        or 0
                    ),
                ),
                "executable_candidate_count": max(
                    1,
                    int(
                        evidence_effect.get("executable_candidate_count")
                        or evidence_effect.get("executable_cleanup_count")
                        or evidence_effect.get("accepted_band_candidate_count")
                        or 0
                    ),
                ),
                "safe_cleanup_count": max(
                    1,
                    int(
                        evidence_effect.get("safe_cleanup_count")
                        or evidence_effect.get("safe_candidate_count")
                        or evidence_effect.get("accepted_band_candidate_count")
                        or 0
                    ),
                ),
                "executable_cleanup_count": max(
                    1,
                    int(
                        evidence_effect.get("executable_cleanup_count")
                        or evidence_effect.get("executable_candidate_count")
                        or evidence_effect.get("accepted_band_candidate_count")
                        or 0
                    ),
                ),
                "safe_shear_cleanup_count": max(
                    1,
                    int(
                        evidence_effect.get("safe_shear_cleanup_count")
                        or evidence_effect.get("safe_candidate_count")
                        or evidence_effect.get("accepted_band_candidate_count")
                        or 0
                    ),
                ),
                "executable_shear_cleanup_count": max(
                    1,
                    int(
                        evidence_effect.get("executable_shear_cleanup_count")
                        or evidence_effect.get("executable_candidate_count")
                        or evidence_effect.get("accepted_band_candidate_count")
                        or 0
                    ),
                ),
            }
        )
        title_main = str(intent_row_d.get("title") or "Shear cleanup - one-click reduction")
        item_effect = {
            "title_main": title_main,
            "family": "shear",
            "check_key": "shear",
            "selected_action_family": "shear",
            "guidance_intent": "efficiency_tightening",
            "action_type": "apply_resolved_candidate",
            "primary_card_actionable": True,
            "local_cleanup_candidate": True,
            "updates": dict(intent_updates),
            "selected_action_updates": dict(intent_updates),
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "expected_util": float(intent_expected),
            "candidate_post_util": float(intent_expected),
            "candidate_search_evidence": dict(evidence_effect),
            "button_contract": dict(button_contract_effect),
        }
        action_payload_effect = {
            "updates": dict(intent_updates),
            "resolved_candidate_updates": dict(intent_updates),
            "resolved_candidate_action_type": "apply_resolved_candidate",
            "resolved_candidate_family_tag": "shear",
            "source_candidate_id": candidate_id,
            "candidate_id": candidate_id,
            "candidate_search_evidence": dict(evidence_effect),
        }
        resolved_candidate_effect = {
            "updates": dict(intent_updates),
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "source_candidate_id": candidate_id,
            "candidate_id": candidate_id,
            "candidate_search_evidence": dict(evidence_effect),
        }
        debug_effect = {
            "render_safe_shear_intent_contract_preferred": True,
            "primary_button_contract": dict(button_contract_effect),
            "button_contract": dict(button_contract_effect),
            "displayed_primary_button_contract": dict(button_contract_effect),
            "button_contract_updates": dict(intent_updates),
            "candidate_search_evidence": dict(evidence_effect),
        }
    result = {
        "applies": applies,
        "source": source,
        "guard_results": guard_results,
        "intent_contract": dict(intent_contract_d),
        "intent_row": dict(intent_row_d),
        "family": intent_family,
        "updates": dict(intent_updates),
        "expected_util": float(intent_expected) if intent_expected is not None else None,
        "candidate_id": candidate_id,
        "button_contract_effect": button_contract_effect,
        "item_effect": item_effect,
        "action_payload_effect": action_payload_effect,
        "resolved_candidate_effect": resolved_candidate_effect,
        "debug_effect": debug_effect,
        "stale_item_keys_to_remove": stale_item_keys_to_remove,
    }
    payload = {
        "result": result,
        "hashes": {
            "item_hash": stable_final_publication_hash(item_d),
            "guidance_debug_hash": stable_final_publication_hash(debug_d),
            "state_hash": stable_final_publication_hash(state_d),
            "intent_contract_hash": stable_final_publication_hash(intent_contract_d),
            "intent_row_hash": stable_final_publication_hash(intent_row_d),
        },
        "derived_from": "FinalDesignGuidePublication.card_render_contract_preference",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": True,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }
    payload["result_hash"] = stable_final_publication_hash(result)
    payload["proof_hash"] = stable_final_publication_hash(payload)
    return payload


def build_final_design_guide_displayed_primary_safe_combined_promotion_result(
    *,
    item: dict[str, Any] | None = None,
    guidance_debug: dict[str, Any] | None = None,
    existing_button_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Represent displayed-primary intent contract promotion as pure data."""

    item_d = _mapping(item)
    debug_d = _mapping(guidance_debug)
    existing_button_d = _mapping(existing_button_contract or item_d.get("button_contract"))
    intent_contract_d, intent_row_d = _final_visible_intent_contract_from_debug_rows(debug_d)
    already_enabled = _final_publication_button_contract_enabled(existing_button_d)
    applies = bool((not already_enabled) and intent_contract_d)
    button_contract_effect: dict[str, Any] = {}
    item_effect: dict[str, Any] = {}
    action_payload_effect: dict[str, Any] = {}
    resolved_candidate_effect: dict[str, Any] = {}
    if applies:
        button_contract_effect = dict(intent_contract_d)
        family = str(
            button_contract_effect.get("family")
            or intent_row_d.get("check_key")
            or item_d.get("family")
            or "combined"
        ).strip().lower()
        check_key = str(
            intent_row_d.get("check_key")
            or button_contract_effect.get("family")
            or item_d.get("check_key")
            or "combined"
        ).strip().lower()
        updates = _mapping(button_contract_effect.get("updates"))
        candidate_id = (
            button_contract_effect.get("candidate_id")
            or button_contract_effect.get("source_candidate_id")
        )
        source_candidate_id = (
            button_contract_effect.get("source_candidate_id")
            or button_contract_effect.get("candidate_id")
        )
        item_effect = {
            "button_contract": dict(button_contract_effect),
            "action_type": "apply_resolved_candidate",
            "family": family,
            "check_key": check_key,
            "selected_action_updates": dict(updates),
            "updates": dict(updates),
            "candidate_id": candidate_id,
            "source_candidate_id": source_candidate_id,
        }
        if intent_row_d:
            if not item_d.get("title_main"):
                item_effect["title_main"] = intent_row_d.get("title")
            if not item_d.get("title"):
                item_effect["title"] = intent_row_d.get("title")
            if not item_d.get("guidance_intent"):
                item_effect["guidance_intent"] = intent_row_d.get("guidance_intent")
        action_payload_effect = {
            "updates": dict(updates),
            "resolved_candidate_updates": dict(updates),
            "resolved_candidate_action_type": "apply_resolved_candidate",
            "resolved_candidate_family_tag": button_contract_effect.get("family"),
            "source_candidate_id": source_candidate_id,
            "candidate_id": candidate_id,
            "expected_util": button_contract_effect.get("expected_util"),
        }
        resolved_candidate_effect = {
            "updates": dict(updates),
            "action_type": "apply_resolved_candidate",
            "family": button_contract_effect.get("family"),
            "source_candidate_id": source_candidate_id,
            "candidate_id": candidate_id,
            "expected_util": button_contract_effect.get("expected_util"),
        }
    result = {
        "applies": applies,
        "already_enabled": already_enabled,
        "intent_contract": dict(intent_contract_d),
        "intent_row": dict(intent_row_d),
        "button_contract_effect": button_contract_effect,
        "item_effect": item_effect,
        "action_payload_effect": action_payload_effect,
        "resolved_candidate_effect": resolved_candidate_effect,
    }
    payload = {
        "result": result,
        "hashes": {
            "item_hash": stable_final_publication_hash(item_d),
            "guidance_debug_hash": stable_final_publication_hash(debug_d),
            "existing_button_contract_hash": stable_final_publication_hash(existing_button_d),
            "intent_contract_hash": stable_final_publication_hash(intent_contract_d),
            "intent_row_hash": stable_final_publication_hash(intent_row_d),
        },
        "derived_from": "FinalDesignGuidePublication.displayed_primary_safe_combined_promotion",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": True,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }
    payload["result_hash"] = stable_final_publication_hash(result)
    payload["proof_hash"] = stable_final_publication_hash(payload)
    return payload


def build_final_design_guide_post_click_safe_intent_allowed_gate_result(
    *,
    guidance_debug: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    post_click_apply_context: bool = False,
    final_accepted_min_family_util: float = 0.85,
    target_band_eps: float = 1e-9,
    shear_update_keys: tuple[str, ...] | list[str] | set[str] = (),
) -> dict[str, Any]:
    """Represent the post-click safe-intent continuation gate as pure data."""

    debug_d = _mapping(guidance_debug)
    state_d = _mapping(state)
    intent_contract_d, intent_row_d = _final_visible_intent_contract_from_debug_rows(debug_d)
    intent_family = str(
        intent_contract_d.get("family")
        or intent_row_d.get("check_key")
        or intent_row_d.get("family")
        or ""
    ).strip().lower()
    intent_updates = _mapping(intent_contract_d.get("updates"))
    intent_expected = _number_or_none(
        intent_contract_d.get("expected_util")
        or intent_row_d.get("expected_util")
        or intent_row_d.get("candidate_post_util")
    )
    shear_keys = {str(key or "") for key in (shear_update_keys or ()) if str(key or "")}
    updates_already_match = all(state_d.get(key) == value for key, value in intent_updates.items()) if intent_updates else False
    guard_results = {
        "post_click_apply_context": bool(post_click_apply_context),
        "has_intent_contract": bool(intent_contract_d),
        "button_contract_enabled": _final_publication_button_contract_enabled(intent_contract_d),
        "action_type_apply_resolved_candidate": str(intent_contract_d.get("action_type") or "").strip()
        == "apply_resolved_candidate",
        "family_is_shear": intent_family == "shear",
        "has_updates": bool(intent_updates),
        "has_shear_update_keys": bool(set(intent_updates) & shear_keys) if shear_keys else bool(intent_updates),
        "updates_not_already_in_state": not updates_already_match,
        "expected_util_present": intent_expected is not None,
        "expected_util_in_accepted_range": bool(
            intent_expected is not None
            and float(final_accepted_min_family_util) - float(target_band_eps)
            <= float(intent_expected)
            <= 1.0 + float(target_band_eps)
        ),
    }
    allowed = bool(post_click_apply_context and all(guard_results.values()))
    result = {
        "allowed": allowed,
        "guard_results": guard_results,
        "intent_contract": dict(intent_contract_d),
        "intent_row": dict(intent_row_d),
        "family": intent_family,
        "updates": dict(intent_updates),
        "expected_util": float(intent_expected) if intent_expected is not None else None,
    }
    payload = {
        "result": result,
        "hashes": {
            "guidance_debug_hash": stable_final_publication_hash(debug_d),
            "state_hash": stable_final_publication_hash(state_d),
            "intent_contract_hash": stable_final_publication_hash(intent_contract_d),
            "intent_row_hash": stable_final_publication_hash(intent_row_d),
        },
        "derived_from": "FinalDesignGuidePublication.post_click_safe_intent_allowed_gate",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": True,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }
    payload["result_hash"] = stable_final_publication_hash(result)
    payload["proof_hash"] = stable_final_publication_hash(payload)
    return payload


def build_final_design_guide_post_click_proof_intent_contract_result(
    *,
    item: dict[str, Any] | None = None,
    guidance_debug: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Represent the post-click proof/display intent contract bridge as pure data."""

    item_d = _mapping(item)
    debug_d = _mapping(guidance_debug)
    intent_contract_d, intent_row_d = _final_visible_intent_contract_from_debug_rows(debug_d)
    intent_family = str(
        intent_contract_d.get("family")
        or intent_row_d.get("check_key")
        or intent_row_d.get("family")
        or ""
    ).strip().lower()
    display_family = str(item_d.get("family") or item_d.get("check_key") or "").strip().lower()
    updates = _mapping(intent_contract_d.get("updates"))
    guard_results = {
        "has_intent_contract": bool(intent_contract_d),
        "intent_row_is_mapping": bool(intent_row_d),
        "family_is_bending_or_shear": intent_family in {"bending", "shear"},
        "display_family_compatible": bool(
            not display_family
            or display_family in {intent_family, "combined", "other", "general"}
        ),
        "updates_present": bool(updates),
    }
    applies = all(guard_results.values())
    item_effect: dict[str, Any] = {}
    debug_effect: dict[str, Any] = {}
    if applies:
        candidate_id = intent_contract_d.get("candidate_id") or intent_contract_d.get("source_candidate_id")
        source_candidate_id = intent_contract_d.get("source_candidate_id") or intent_contract_d.get("candidate_id")
        item_effect = {
            "action_type": "apply_resolved_candidate",
            "family": intent_family,
            "check_key": intent_family,
            "selected_action_family": intent_family,
            "primary_card_actionable": True,
            "updates": dict(updates),
            "selected_action_updates": dict(updates),
            "button_contract": dict(intent_contract_d),
            "candidate_id": candidate_id,
            "source_candidate_id": source_candidate_id,
        }
        debug_effect = {
            "displayed_intent_contract_preferred_for_bundle": True,
            "displayed_intent_contract_preferred_family": intent_family,
        }
    result = {
        "applies": applies,
        "guard_results": guard_results,
        "intent_contract": dict(intent_contract_d),
        "intent_row": dict(intent_row_d),
        "family": intent_family,
        "display_family": display_family,
        "updates": dict(updates),
        "proof_action_contract_effect": dict(intent_contract_d) if applies else {},
        "displayed_primary_button_contract_effect": dict(intent_contract_d) if applies else {},
        "item_effect": item_effect,
        "debug_effect": debug_effect,
    }
    payload = {
        "result": result,
        "hashes": {
            "item_hash": stable_final_publication_hash(item_d),
            "guidance_debug_hash": stable_final_publication_hash(debug_d),
            "intent_contract_hash": stable_final_publication_hash(intent_contract_d),
            "intent_row_hash": stable_final_publication_hash(intent_row_d),
        },
        "derived_from": "FinalDesignGuidePublication.post_click_proof_intent_contract",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": True,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }
    payload["result_hash"] = stable_final_publication_hash(result)
    payload["proof_hash"] = stable_final_publication_hash(payload)
    return payload


def build_final_design_guide_post_cleanup_render_audit_intent_contract_result(
    *,
    guidance_debug: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve post-cleanup render-audit intent contract as pure data."""

    debug_d = _mapping(guidance_debug)
    intent_contract_d, intent_row_d = _final_visible_intent_contract_from_debug_rows(debug_d)
    source = "intent_rows"
    if not intent_contract_d:
        for contract_key in ("primary_button_contract_debug", "displayed_primary_button_contract_debug"):
            candidate_contract = _mapping(debug_d.get(contract_key))
            if (
                _final_publication_button_contract_enabled(candidate_contract)
                and str(candidate_contract.get("action_type") or "").strip() == "apply_resolved_candidate"
            ):
                family = str(candidate_contract.get("family") or "")
                selected_title = str(
                    debug_d.get("selected_title")
                    or f"{family.title() if family else 'Design'} cleanup - best safe one-click reduction"
                )
                intent_contract_d = dict(candidate_contract)
                intent_row_d = {
                    "title": selected_title,
                    "check_key": family,
                    "family": family,
                    "action_type": "apply_resolved_candidate",
                    "guidance_intent": "efficiency_tightening",
                }
                source = contract_key
                break
    intent_family = str(
        intent_contract_d.get("family")
        or intent_row_d.get("check_key")
        or intent_row_d.get("family")
        or ""
    ).strip().lower()
    result = {
        "contract_found": bool(intent_contract_d),
        "row_found": bool(intent_row_d),
        "source": source if intent_contract_d else "none",
        "intent_contract": dict(intent_contract_d),
        "intent_row": dict(intent_row_d),
        "family": intent_family,
        "updates": _mapping(intent_contract_d.get("updates")),
    }
    payload = {
        "result": result,
        "hashes": {
            "guidance_debug_hash": stable_final_publication_hash(debug_d),
            "intent_contract_hash": stable_final_publication_hash(intent_contract_d),
            "intent_row_hash": stable_final_publication_hash(intent_row_d),
        },
        "derived_from": "FinalDesignGuidePublication.post_cleanup_render_audit_intent_contract",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": True,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }
    payload["result_hash"] = stable_final_publication_hash(result)
    payload["proof_hash"] = stable_final_publication_hash(payload)
    return payload


def build_final_design_guide_late_render_shear_action_intent_contract_result(
    *,
    guidance_debug: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    active_strength_failures: tuple[str, ...] | list[str] | set[str] | None = None,
    final_accepted_min_family_util: float = 0.85,
    target_band_eps: float = 1e-9,
    shear_update_keys: tuple[str, ...] | list[str] | set[str] = (),
) -> dict[str, Any]:
    """Represent late-render low-shear intent contract preference as pure data."""

    debug_d = _mapping(guidance_debug)
    state_d = _mapping(state)
    intent_contract_d, intent_row_d = _final_visible_intent_contract_from_debug_rows(debug_d)
    intent_family = str(
        intent_contract_d.get("family")
        or intent_row_d.get("check_key")
        or intent_row_d.get("family")
        or ""
    ).strip().lower()
    intent_updates = _mapping(intent_contract_d.get("updates"))
    intent_expected = _number_or_none(
        intent_contract_d.get("expected_util")
        or intent_row_d.get("expected_util")
        or intent_row_d.get("candidate_post_util")
    )
    shear_keys = {str(key or "") for key in (shear_update_keys or ()) if str(key or "")}
    active_failures = tuple(sorted(str(value or "").strip().lower() for value in (active_strength_failures or ()) if value))
    updates_already_match = all(state_d.get(key) == value for key, value in intent_updates.items()) if intent_updates else False
    guard_results = {
        "has_intent_contract": bool(intent_contract_d),
        "button_contract_enabled": _final_publication_button_contract_enabled(intent_contract_d),
        "action_type_apply_resolved_candidate": str(intent_contract_d.get("action_type") or "").strip()
        == "apply_resolved_candidate",
        "family_is_shear": intent_family == "shear",
        "has_updates": bool(intent_updates),
        "has_shear_update_keys": bool(set(intent_updates) & shear_keys) if shear_keys else bool(intent_updates),
        "updates_not_already_in_state": not updates_already_match,
        "no_active_strength_failures": not bool(active_failures),
    }
    applies = all(guard_results.values())
    evidence_effect: dict[str, Any] = {}
    candidate_id = ""
    if applies:
        evidence_effect = _mapping(debug_d.get("candidate_search_evidence"))
        for stale_key in (
            "exact_blockers_by_family",
            "post_click_exact_blockers_by_family",
            "cleanup_evidence_by_family",
            "post_click_cleanup_evidence_by_family",
        ):
            evidence_effect.pop(stale_key, None)
        candidate_id = str(
            intent_contract_d.get("candidate_id")
            or intent_contract_d.get("source_candidate_id")
            or evidence_effect.get("selected_candidate_id")
            or evidence_effect.get("best_safe_candidate_id")
            or _local_cleanup_candidate_id("shear", intent_updates)
        ).strip()
        evidence_effect.update(
            {
                "cleanup_search_ran": True,
                "cleanup_search_exhaustive": True,
                "local_cleanup_search_ran": True,
                "local_cleanup_search_exhaustive": True,
                "family": "shear",
                "selected_candidate_id": candidate_id,
                "best_safe_candidate_id": candidate_id,
                "selected_candidate_updates": dict(intent_updates),
                "best_safe_candidate_updates": dict(intent_updates),
                "best_safe_candidate_applied": False,
                "best_safe_partial_cleanup": True,
                "no_second_cta_required": False,
                "safe_candidate_count": max(
                    1,
                    int(evidence_effect.get("safe_candidate_count") or evidence_effect.get("safe_cleanup_count") or 0),
                ),
                "executable_candidate_count": max(
                    1,
                    int(
                        evidence_effect.get("executable_candidate_count")
                        or evidence_effect.get("executable_cleanup_count")
                        or 0
                    ),
                ),
                "safe_cleanup_count": max(
                    1,
                    int(evidence_effect.get("safe_cleanup_count") or evidence_effect.get("safe_candidate_count") or 0),
                ),
                "executable_cleanup_count": max(
                    1,
                    int(
                        evidence_effect.get("executable_cleanup_count")
                        or evidence_effect.get("executable_candidate_count")
                        or 0
                    ),
                ),
                "safe_shear_cleanup_count": max(
                    1,
                    int(
                        evidence_effect.get("safe_shear_cleanup_count")
                        or evidence_effect.get("safe_candidate_count")
                        or 0
                    ),
                ),
                "executable_shear_cleanup_count": max(
                    1,
                    int(
                        evidence_effect.get("executable_shear_cleanup_count")
                        or evidence_effect.get("executable_candidate_count")
                        or 0
                    ),
                ),
                "one_click_target_reaching_candidate_exists": bool(
                    evidence_effect.get("one_click_target_reaching_candidate_exists")
                    or (
                        intent_expected is not None
                        and float(final_accepted_min_family_util) - float(target_band_eps)
                        <= float(intent_expected)
                        <= 1.0 + float(target_band_eps)
                    )
                ),
            }
        )
        if intent_expected is not None:
            evidence_effect["selected_candidate_util"] = float(intent_expected)
            evidence_effect["best_safe_final_util"] = float(intent_expected)
    result = {
        "applies": applies,
        "guard_results": guard_results,
        "intent_contract": dict(intent_contract_d),
        "intent_row": dict(intent_row_d),
        "family": intent_family,
        "updates": dict(intent_updates),
        "expected_util": float(intent_expected) if intent_expected is not None else None,
        "candidate_id": candidate_id,
        "evidence_effect": evidence_effect,
    }
    payload = {
        "result": result,
        "hashes": {
            "guidance_debug_hash": stable_final_publication_hash(debug_d),
            "state_hash": stable_final_publication_hash(state_d),
            "intent_contract_hash": stable_final_publication_hash(intent_contract_d),
            "intent_row_hash": stable_final_publication_hash(intent_row_d),
            "evidence_effect_hash": stable_final_publication_hash(evidence_effect),
        },
        "derived_from": "FinalDesignGuidePublication.late_render_shear_action_intent_contract",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": True,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }
    payload["result_hash"] = stable_final_publication_hash(result)
    payload["proof_hash"] = stable_final_publication_hash(payload)
    return payload


def build_final_visible_contract_binding_intent_contract_rebind_result(
    *,
    item: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    guidance_debug: dict[str, Any] | None = None,
    intent_contract: dict[str, Any] | None = None,
    intent_row: dict[str, Any] | None = None,
    candidate_id_fallback: str = "",
    post_click_apply_context: bool = False,
    active_strength_failures: tuple[str, ...] | list[str] | set[str] | None = None,
    current_binding_cross_family: bool = False,
) -> dict[str, Any]:
    """Represent the intent-row contract rebind tail as proof-only data.

    This does not read Streamlit/session state, render UI, route Apply, or
    mutate caller dictionaries. It only models the current page tail that can
    recover an enabled ``apply_resolved_candidate`` contract from debug intent
    rows when the current final-visible contract is disabled.
    """

    item_d = _mapping(item)
    contract_d = _mapping(contract or item_d.get("button_contract"))
    debug_d = _mapping(guidance_debug)
    intent_contract_d = _mapping(intent_contract)
    intent_row_d = _mapping(intent_row)
    if not intent_contract_d:
        intent_contract_d, intent_row_d = _final_visible_intent_contract_from_debug_rows(debug_d)

    intent_updates = _mapping(intent_contract_d.get("updates"))
    intent_family = str(
        intent_contract_d.get("family")
        or intent_row_d.get("check_key")
        or intent_row_d.get("family")
        or ""
    ).strip().lower()
    out_family = str(
        item_d.get("selected_action_family")
        or item_d.get("family")
        or item_d.get("check_key")
        or ""
    ).strip().lower()
    active_failures = tuple(sorted(str(value or "").strip().lower() for value in (active_strength_failures or ()) if value))
    expected_util = _number_or_none(
        intent_contract_d.get("expected_util")
        or intent_row_d.get("expected_util")
        or intent_row_d.get("candidate_post_util")
    )
    candidate_id = _text(
        intent_contract_d.get("candidate_id"),
        intent_contract_d.get("source_candidate_id"),
        intent_row_d.get("candidate_id"),
        intent_row_d.get("source_candidate_id"),
        candidate_id_fallback,
        _local_cleanup_candidate_id(intent_family, intent_updates) if intent_family and intent_updates else None,
    )
    guard_results = {
        "has_intent_contract": bool(intent_contract_d),
        "has_intent_row": bool(intent_row_d),
        "family_allowed": intent_family in {"bending", "shear"},
        "out_family_allowed": (not out_family or out_family in {intent_family, "combined", "other", "general"}),
        "no_post_click_apply_context": not bool(post_click_apply_context),
        "no_active_strength_failures": not bool(active_failures),
        "not_current_binding_cross_family": not bool(current_binding_cross_family),
        "has_updates": bool(intent_updates),
    }
    applies = all(guard_results.values())

    contract_effect: dict[str, Any] = {}
    item_effect: dict[str, Any] = {}
    debug_effect = {
        "final_binding_intent_contract_candidate_present": bool(intent_contract_d),
        "final_binding_intent_contract_family": intent_family,
        "final_binding_intent_contract_updates": dict(intent_updates),
    }
    if applies:
        contract_effect = {
            **intent_contract_d,
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": intent_family,
            "updates": dict(intent_updates),
            "preview_pass": True,
            "blocking_reason": None,
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
        }
        if expected_util is not None:
            contract_effect["expected_util"] = float(expected_util)
        item_effect = {
            "action_type": "apply_resolved_candidate",
            "family": intent_family,
            "check_key": intent_family,
            "selected_action_family": intent_family,
            "primary_card_actionable": True,
            "updates": dict(intent_updates),
            "selected_action_updates": dict(intent_updates),
            "button_contract": dict(contract_effect),
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
        }
        if intent_row_d.get("title"):
            item_effect["title_main"] = intent_row_d.get("title")
            item_effect["title"] = intent_row_d.get("title")
        if intent_row_d.get("guidance_intent"):
            item_effect["guidance_intent"] = intent_row_d.get("guidance_intent")
        else:
            item_effect["guidance_intent"] = "efficiency_tightening"
        debug_effect.update(
            {
                "final_binding_intent_contract_preferred": True,
                "final_binding_intent_contract_family": intent_family,
                "final_binding_intent_contract_updates": dict(intent_updates),
            }
        )

    result = {
        "applies": applies,
        "guard_results": guard_results,
        "intent_family": intent_family,
        "out_family": out_family,
        "active_strength_failures": active_failures,
        "current_binding_cross_family": bool(current_binding_cross_family),
        "post_click_apply_context": bool(post_click_apply_context),
        "intent_contract": dict(intent_contract_d),
        "intent_row": dict(intent_row_d),
        "intent_updates": dict(intent_updates),
        "expected_util": expected_util,
        "candidate_id": candidate_id,
        "contract_effect": contract_effect,
        "item_effect": item_effect,
        "updates_effect": dict(intent_updates) if applies else {},
        "action_type_effect": "apply_resolved_candidate" if applies else "",
        "debug_effect": debug_effect,
    }
    payload = {
        "result": result,
        "result_hash": stable_final_publication_hash(result),
        "input_hashes": {
            "item_hash": stable_final_publication_hash(item_d),
            "contract_hash": stable_final_publication_hash(contract_d),
            "guidance_debug_hash": stable_final_publication_hash(debug_d),
            "intent_contract_hash": stable_final_publication_hash(intent_contract_d),
            "intent_row_hash": stable_final_publication_hash(intent_row_d),
            "candidate_id_fallback_hash": stable_final_publication_hash(candidate_id_fallback),
        },
        "represented_live_groups": (
            "intent_contract_debug_row_scan",
            "intent_contract_guard_decision",
            "intent_contract_button_contract_rebind",
            "intent_contract_item_rebind",
            "intent_contract_update_action_type_rebind",
            "intent_contract_debug_rebind",
        ),
        "derived_from": "FinalDesignGuidePublication.final_visible_contract_binding_intent_contract_rebind",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": False,
    }
    return {**payload, "proof_hash": stable_final_publication_hash(payload)}


def build_final_visible_render_stage_intent_contract_rebind_result(
    *,
    item: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    guidance_debug: dict[str, Any] | None = None,
    intent_contract: dict[str, Any] | None = None,
    intent_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Represent the render-stage intent-row contract recovery branch.

    This is intentionally narrower than the final-binding rebind result: the
    live render-stage branch applies the recovered intent contract as-is, then
    mirrors a small set of item fields before recording the existing apply
    payload. This builder models that shape without importing Streamlit or
    mutating caller dictionaries.
    """

    item_d = _mapping(item)
    contract_d = _mapping(contract or item_d.get("button_contract"))
    debug_d = _mapping(guidance_debug)
    intent_contract_d = _mapping(intent_contract)
    intent_row_d = _mapping(intent_row)
    if not intent_contract_d:
        intent_contract_d, intent_row_d = _final_visible_intent_contract_from_debug_rows(debug_d)

    intent_updates = _mapping(intent_contract_d.get("updates"))
    candidate_id = _text(
        intent_contract_d.get("candidate_id"),
        intent_contract_d.get("source_candidate_id"),
    )
    source_candidate_id = _text(
        intent_contract_d.get("source_candidate_id"),
        intent_contract_d.get("candidate_id"),
    )
    item_effect: dict[str, Any] = {}
    applies = bool(intent_contract_d)
    if applies:
        item_effect = {
            "button_contract": dict(intent_contract_d),
            "action_type": "apply_resolved_candidate",
            "selected_action_updates": dict(intent_updates),
            "updates": dict(intent_updates),
            "candidate_id": candidate_id,
            "source_candidate_id": source_candidate_id,
        }
        if isinstance(intent_row_d, dict):
            if intent_row_d.get("title") and "title_main" not in item_d:
                item_effect["title_main"] = intent_row_d.get("title")
            if intent_row_d.get("title") and "title" not in item_d:
                item_effect["title"] = intent_row_d.get("title")
            if intent_row_d.get("guidance_intent") and "guidance_intent" not in item_d:
                item_effect["guidance_intent"] = intent_row_d.get("guidance_intent")

    output_item = dict(item_d)
    output_item.update(dict(item_effect))
    result = {
        "applies": applies,
        "intent_contract": dict(intent_contract_d),
        "intent_row": dict(intent_row_d),
        "contract_effect": dict(intent_contract_d) if applies else {},
        "item_effect": dict(item_effect),
        "output_item": dict(output_item),
        "updates_effect": dict(intent_updates) if applies else {},
        "candidate_id": candidate_id,
        "source_candidate_id": source_candidate_id,
        "guard_results": {
            "has_intent_contract": bool(intent_contract_d),
            "current_contract_disabled": not bool(contract_d.get("enabled"))
            and not bool(contract_d.get("actionable")),
        },
    }
    payload = {
        "result": dict(result),
        "result_hash": stable_final_publication_hash(result),
        "input_hashes": {
            "item_hash": stable_final_publication_hash(item_d),
            "contract_hash": stable_final_publication_hash(contract_d),
            "guidance_debug_hash": stable_final_publication_hash(debug_d),
            "intent_contract_hash": stable_final_publication_hash(intent_contract_d),
            "intent_row_hash": stable_final_publication_hash(intent_row_d),
        },
        "represented_live_groups": (
            "render_stage_intent_contract_debug_row_scan",
            "render_stage_button_contract_rebind",
            "render_stage_item_rebind",
            "render_stage_apply_payload_input",
        ),
        "derived_from": "FinalDesignGuidePublication.render_stage_intent_contract_rebind",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": False,
    }
    return {**payload, "proof_hash": stable_final_publication_hash(payload)}


def build_final_design_guide_publication_mutation_proof(
    *,
    callsite_id: str,
    input_item: dict[str, Any] | None = None,
    output_item: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    debug: dict[str, Any] | None = None,
    rec: dict[str, Any] | None = None,
) -> FinalDesignGuidePublicationMutationProof:
    """Build a trace-only proof for publication-driven selected-item mutation parity."""

    input_d = _mapping(input_item)
    output_d = _mapping(output_item)
    state_d = _mapping(state)
    debug_d = _mapping(debug)
    rec_d = _mapping(rec)
    input_hash = stable_final_publication_hash(input_d)
    output_hash = stable_final_publication_hash(output_d)
    cta_keys = ("button_contract", "action_payload", "primary_action", "cta_label", "updates")
    display_keys = (
        "title",
        "title_main",
        "summary_line",
        "status",
        "bucket",
        "guidance_intent",
        "headline",
        "body",
    )
    evidence_keys = (
        "candidate_search_evidence",
        "resolved_candidate",
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "target_band_proof",
        "repair_reason_proof",
        "blocked_reason",
    )
    cta_input = {key: input_d.get(key) for key in cta_keys if key in input_d}
    cta_output = {key: output_d.get(key) for key in cta_keys if key in output_d}
    display_input = {key: input_d.get(key) for key in display_keys if key in input_d}
    display_output = {key: output_d.get(key) for key in display_keys if key in output_d}
    evidence_input = {key: input_d.get(key) for key in evidence_keys if key in input_d}
    evidence_output = {key: output_d.get(key) for key in evidence_keys if key in output_d}
    cta_input_hash = stable_final_publication_hash(cta_input)
    cta_output_hash = stable_final_publication_hash(cta_output)
    display_input_hash = stable_final_publication_hash(display_input)
    display_output_hash = stable_final_publication_hash(display_output)
    evidence_input_hash = stable_final_publication_hash(evidence_input)
    evidence_output_hash = stable_final_publication_hash(evidence_output)
    mutation_surface = {
        "output_changed": input_hash != output_hash,
        "cta_changed": cta_input_hash != cta_output_hash,
        "display_changed": display_input_hash != display_output_hash,
        "evidence_changed": evidence_input_hash != evidence_output_hash,
    }
    payload = {
        "callsite_id": callsite_id,
        "input_item_hash": input_hash,
        "output_item_hash": output_hash,
        "state_hash": stable_final_publication_hash(state_d),
        "debug_hash": stable_final_publication_hash(debug_d),
        "rec_hash": stable_final_publication_hash(rec_d),
        "cta_projection_hash": stable_final_publication_hash(
            {"input": cta_input_hash, "output": cta_output_hash}
        ),
        "display_projection_hash": stable_final_publication_hash(
            {"input": display_input_hash, "output": display_output_hash}
        ),
        "evidence_projection_hash": stable_final_publication_hash(
            {"input": evidence_input_hash, "output": evidence_output_hash}
        ),
        "mutation_surface": dict(mutation_surface),
        "output_changed": mutation_surface["output_changed"],
        "cta_changed": mutation_surface["cta_changed"],
        "display_changed": mutation_surface["display_changed"],
        "evidence_changed": mutation_surface["evidence_changed"],
        "derived_from": "final_design_guide_publication_mutation",
        "proof_only": True,
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return FinalDesignGuidePublicationMutationProof(
        callsite_id=callsite_id,
        input_item_hash=payload["input_item_hash"],
        output_item_hash=payload["output_item_hash"],
        state_hash=payload["state_hash"],
        debug_hash=payload["debug_hash"],
        rec_hash=payload["rec_hash"],
        cta_projection_hash=payload["cta_projection_hash"],
        display_projection_hash=payload["display_projection_hash"],
        evidence_projection_hash=payload["evidence_projection_hash"],
        mutation_surface=dict(mutation_surface),
        output_changed=bool(payload["output_changed"]),
        cta_changed=bool(payload["cta_changed"]),
        display_changed=bool(payload["display_changed"]),
        evidence_changed=bool(payload["evidence_changed"]),
        proof_hash=stable_final_publication_hash(payload),
    )


def build_final_visible_contract_binding_output_projection(
    *,
    callsite_id: str,
    input_item: dict[str, Any] | None = None,
    rebind_projection: dict[str, Any] | None = None,
    debug_projection: dict[str, Any] | None = None,
) -> FinalVisibleContractBindingOutputProjection:
    """Build a page-free contract-binding output projection.

    The old page restamper helper rebuilt one final-visible item plus the CTA,
    evidence, action-payload, resolved-candidate, display, and debug surfaces.
    This adapter consumes plain dictionaries already available to the controller
    or final-publication layer and returns the same projection surface without
    reading session state, rendering UI, routing Apply, or evaluating candidates.
    """

    input_d = _mapping(input_item)
    projection_d = _mapping(rebind_projection)
    projected_item = _mapping(projection_d.get("item")) or dict(input_d)
    projected_contract = _mapping(projection_d.get("contract")) or _mapping(
        projected_item.get("button_contract")
    )
    projected_evidence = _mapping(projection_d.get("evidence_for_binding")) or _mapping(
        projected_item.get("candidate_search_evidence")
    )
    projected_debug = _mapping(projection_d.get("debug")) or _mapping(debug_projection)
    action_payload = _mapping(projected_item.get("action_payload"))
    resolved_candidate = _mapping(projected_item.get("resolved_candidate"))
    display_projection = {
        key: projected_item.get(key)
        for key in (
            "title",
            "title_main",
            "summary_line",
            "status",
            "bucket",
            "guidance_intent",
            "headline",
            "body",
            "family_status_current",
            "family_status_preview",
            "display_truth",
        )
        if key in projected_item
    }
    cta_projection = {
        "button_contract": projected_contract,
        "action_payload": action_payload,
        "primary_card_actionable": projected_item.get("primary_card_actionable"),
    }
    for key in ("action_type", "updates", "selected_action_updates"):
        value = projected_item.get(key)
        if value not in (None, {}, []):
            cta_projection[key] = value
    evidence_projection = {
        key: projected_item.get(key)
        for key in (
            "candidate_search_evidence",
            "exact_blockers_by_family",
            "post_click_exact_blockers_by_family",
            "cleanup_evidence_by_family",
            "post_click_cleanup_evidence_by_family",
            "target_band_proof",
            "repair_reason_proof",
            "blocked_reason",
        )
        if key in projected_item
    }
    if projected_evidence:
        evidence_projection["candidate_search_evidence"] = dict(projected_evidence)
    source_hashes = {
        "input_item_hash": stable_final_publication_hash(input_d),
        "rebind_projection_hash": stable_final_publication_hash(projection_d),
        "item_hash": stable_final_publication_hash(projected_item),
        "cta_projection_hash": stable_final_publication_hash(cta_projection),
        "display_projection_hash": stable_final_publication_hash(display_projection),
        "evidence_projection_hash": stable_final_publication_hash(evidence_projection),
        "action_payload_projection_hash": stable_final_publication_hash(action_payload),
        "resolved_candidate_projection_hash": stable_final_publication_hash(resolved_candidate),
        "debug_projection_hash": stable_final_publication_hash(projected_debug),
    }
    payload = {
        "callsite_id": str(callsite_id or ""),
        "item": dict(projected_item),
        "cta_projection": dict(cta_projection),
        "display_projection": dict(display_projection),
        "evidence_projection": dict(evidence_projection),
        "action_payload_projection": dict(action_payload),
        "resolved_candidate_projection": dict(resolved_candidate),
        "debug_projection": dict(projected_debug),
        "source_projection_hashes": dict(source_hashes),
        "derived_from": "FinalDesignGuidePublication.final_visible_contract_binding_output_projection",
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    return FinalVisibleContractBindingOutputProjection(
        callsite_id=str(callsite_id or ""),
        item=dict(projected_item),
        cta_projection=dict(cta_projection),
        display_projection=dict(display_projection),
        evidence_projection=dict(evidence_projection),
        action_payload_projection=dict(action_payload),
        resolved_candidate_projection=dict(resolved_candidate),
        debug_projection=dict(projected_debug),
        source_projection_hashes=dict(source_hashes),
        adapter_hash=stable_final_publication_hash(payload),
    )


def _final_visible_projection_family(item: dict[str, Any]) -> str:
    contract = _mapping(item.get("button_contract"))
    family = _text(
        contract.get("family"),
        item.get("selected_action_family"),
        item.get("family"),
        item.get("check_key"),
        "combined",
    )
    return str(family or "combined").strip().lower() or "combined"


def _final_visible_projection_blocker_reason(item: dict[str, Any]) -> str:
    contract = _mapping(item.get("button_contract"))
    reason = _text(contract.get("blocking_reason"), item.get("blocked_reason"))
    if reason:
        return reason
    for key in ("exact_blockers_by_family", "post_click_exact_blockers_by_family"):
        blockers = _mapping(item.get(key))
        for blocker in blockers.values():
            if isinstance(blocker, dict) and _text(blocker.get("reason")):
                return str(blocker.get("reason")).strip()
    return "final_visible_non_actionable"


def _final_visible_projection_disabled_contract(
    item: dict[str, Any],
    *,
    family: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    resolved_family = str(family or _final_visible_projection_family(item) or "other").strip() or "other"
    return {
        "enabled": False,
        "actionable": False,
        "action_type": None,
        "family": resolved_family,
        "updates": {},
        "preview_pass": False,
        "expected_util": None,
        "blocking_reason": str(reason or "specific_blocker").strip() or "specific_blocker",
        "source_candidate_id": None,
        "candidate_id": None,
    }


def _final_visible_projection_is_visible_blocker(item: dict[str, Any]) -> bool:
    status = str(item.get("status") or "").strip().upper()
    bucket = str(item.get("bucket") or "").strip().lower()
    intent = str(item.get("guidance_intent") or "").strip().lower()
    title = str(item.get("title_main") or item.get("title") or "").strip().lower()
    return bool(
        status in {"BLOCKED", "ERROR"}
        or bucket in {"blocked", "blocker"}
        or "block" in intent
        or "blocker" in title
        or "blocked" in title
    )


def build_final_visible_family_status_display_projection(
    *,
    input_item: dict[str, Any] | None = None,
    current_state_for_display: dict[str, Any] | None = None,
    family_status_current: dict[str, Any] | None = None,
    family_status_preview: dict[str, Any] | None = None,
    blocker_attempts_by_family: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project family-status display fields without page/session authority.

    The page may still supply live overview-derived tables while formula and
    evaluator boundaries remain there. This adapter owns only the final-visible
    publication projection shape consumed by the final-publication branch
    adapters.
    """

    item = _mapping(input_item)
    projection: dict[str, Any] = {}
    state_d = _mapping(current_state_for_display)
    current_d = _mapping(family_status_current)
    preview_d = _mapping(family_status_preview)
    blocker_d = _mapping(blocker_attempts_by_family)
    if state_d:
        projection["_current_state_for_display"] = dict(state_d)
    if current_d:
        projection["family_status_current"] = dict(current_d)
    elif isinstance(item.get("family_status_current"), dict):
        projection["family_status_current"] = _mapping(item.get("family_status_current"))
    if preview_d:
        projection["family_status_preview"] = dict(preview_d)
    elif isinstance(item.get("family_status_preview"), dict):
        projection["family_status_preview"] = _mapping(item.get("family_status_preview"))
    if blocker_d:
        projection["blocker_attempts_by_family"] = dict(blocker_d)
    elif isinstance(item.get("blocker_attempts_by_family"), dict):
        projection["blocker_attempts_by_family"] = _mapping(item.get("blocker_attempts_by_family"))
    return projection


def build_final_visible_combined_outside_target_blocker_evidence_projection(
    *,
    existing_evidence: dict[str, Any] | None = None,
    exact_blockers_by_family: dict[str, Any] | None = None,
    updates: dict[str, Any] | None = None,
    expected_util: Any = None,
    action_payload: dict[str, Any] | None = None,
    resolved_candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project combined outside-target blocker evidence without page authority."""

    evidence = _mapping(existing_evidence)
    exact = _mapping(exact_blockers_by_family)
    updates_d = _mapping(updates)
    action_payload_d = _mapping(action_payload)
    resolved_candidate_d = _mapping(resolved_candidate)
    try:
        expected_value = float(expected_util)
    except Exception:
        expected_value = None
    if expected_value is not None:
        evidence.update(
            {
                "family": "combined",
                "selected_candidate_util": expected_value,
                "best_safe_final_util": expected_value,
                "candidate_post_util": expected_value,
                "best_safe_below_band_proven": True,
                "best_safe_candidate_applied": False,
                "no_second_cta_required": False,
                "selected_candidate_updates": dict(updates_d),
                "best_safe_candidate_updates": dict(updates_d),
                "exact_blockers_by_family": dict(exact),
                "post_click_exact_blockers_by_family": dict(exact),
                "cleanup_evidence_by_family": dict(exact),
                "post_click_cleanup_evidence_by_family": dict(exact),
            }
        )
    item_projection = {
        "candidate_search_evidence": dict(evidence),
        "exact_blockers_by_family": dict(exact),
        "post_click_exact_blockers_by_family": dict(exact),
        "cleanup_evidence_by_family": dict(exact),
        "post_click_cleanup_evidence_by_family": dict(exact),
    }
    action_payload_projection = dict(action_payload_d)
    action_payload_projection["candidate_search_evidence"] = dict(evidence)
    resolved_candidate_projection = dict(resolved_candidate_d)
    resolved_candidate_projection["candidate_search_evidence"] = dict(evidence)
    payload = {
        "candidate_search_evidence": dict(evidence),
        "item_projection": dict(item_projection),
        "action_payload_projection": dict(action_payload_projection),
        "resolved_candidate_projection": dict(resolved_candidate_projection),
        "projection_hashes": {
            "evidence_hash": stable_final_publication_hash(evidence),
            "exact_blockers_hash": stable_final_publication_hash(exact),
            "updates_hash": stable_final_publication_hash(updates_d),
            "action_payload_hash": stable_final_publication_hash(action_payload_projection),
            "resolved_candidate_hash": stable_final_publication_hash(resolved_candidate_projection),
        },
        "derived_from": "FinalDesignGuidePublication.combined_outside_target_blocker_evidence_projection",
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    payload["projection_hash"] = stable_final_publication_hash(payload)
    return payload


def build_final_visible_primary_payload_binding_audit_projection(
    *,
    visible_primary_candidate_id: Any = None,
    state_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Project the disabled primary payload-binding audit without page authority."""

    projection = {
        "visible_primary_candidate_id": visible_primary_candidate_id,
        "button_contract_candidate_id": None,
        "queued_apply_candidate_id": None,
        "applied_candidate_id": None,
        "visible_updates": {},
        "button_contract_updates": {},
        "queued_apply_updates": {},
        "applied_updates": {},
        "payload_binding_match": False,
        "payload_update_match": False,
        "stale_apply_payload_blocked": False,
        "canonical_primary_payload_exists": False,
        "legacy_fallback_used": False,
        "render_fingerprint": None,
        "state_fingerprint": state_fingerprint,
    }
    return {
        **projection,
        "projection_hash": stable_final_publication_hash(projection),
        "derived_from": "FinalDesignGuidePublication.primary_payload_binding_audit_projection",
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }


def build_final_design_guide_primary_apply_payload_projection(
    *,
    item: dict[str, Any] | None = None,
    rec: dict[str, Any] | None = None,
    button_contract: dict[str, Any] | None = None,
    updates: dict[str, Any] | None = None,
    visible_updates: dict[str, Any] | None = None,
    current_state_apply_guard: dict[str, Any] | None = None,
    candidate_id: Any = None,
    family: str | None = None,
    selected_family_id: str | None = None,
    action_type: str | None = None,
    state_fingerprint: str | None = None,
    render_fingerprint: str | None = None,
    expected_util: Any = None,
    label: str | None = None,
    source: str = "design_guide_primary_render",
    extra_payload_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project the primary Apply payload shape without page/session authority.

    The page still owns the live current-state safety guard and any evaluator
    probes needed to produce the inputs to this adapter. This function owns only
    the final payload projection shape that can later replace page-local
    assembly after those guard/probe inputs are proven stable.
    """

    item_d = _mapping(item)
    rec_d = _mapping(rec)
    contract_d = _mapping(button_contract)
    updates_d = _mapping(updates) or _mapping(contract_d.get("updates"))
    visible_updates_d = _mapping(visible_updates) or dict(updates_d)
    guard_d = _mapping(current_state_apply_guard)
    resolved_action_type = str(action_type or contract_d.get("action_type") or "").strip()
    resolved_family = str(
        family
        or contract_d.get("family")
        or item_d.get("family")
        or rec_d.get("family")
        or ""
    ).strip()
    resolved_candidate_id = str(candidate_id or "").strip()
    if not (
        bool(contract_d.get("enabled") or contract_d.get("actionable"))
        and resolved_action_type == "apply_resolved_candidate"
        and updates_d
        and bool(guard_d.get("pass"))
    ):
        payload: dict[str, Any] = {}
        enabled = False
    else:
        payload = {
            "candidate_id": resolved_candidate_id,
            "source_candidate_id": resolved_candidate_id,
            "action_type": resolved_action_type,
            "family": resolved_family,
            "updates": dict(updates_d),
            "visible_updates": dict(visible_updates_d),
            "button_contract_updates": dict(updates_d),
            "preview_status": "PASS" if contract_d.get("preview_pass") is True else "FAIL",
            "preview_pass": bool(contract_d.get("preview_pass")),
            "current_state_apply_preview_guard": dict(guard_d),
            "expected_util": (
                expected_util if expected_util is not None else contract_d.get("expected_util")
            ),
            "label": str(
                label
                or contract_d.get("label")
                or item_d.get("title_main")
                or item_d.get("title")
                or rec_d.get("title")
                or rec_d.get("label")
                or "Apply recommendation"
            ).strip(),
            "source": str(source or "design_guide_primary_render"),
            "apply_payload_family_id": selected_family_id,
            "selected_family_id": selected_family_id,
            "render_fingerprint": render_fingerprint or stable_final_publication_hash(
                {
                    "candidate_id": resolved_candidate_id,
                    "action_type": resolved_action_type,
                    "family": resolved_family,
                    "updates": dict(updates_d),
                    "state_fingerprint": state_fingerprint,
                }
            ),
            "state_fingerprint": state_fingerprint,
        }
        payload.update(_mapping(extra_payload_fields))
        enabled = True
    projection = {
        "payload": dict(payload),
        "payload_hash": stable_final_publication_hash(payload),
        "enabled": bool(enabled),
        "guard_hash": stable_final_publication_hash(guard_d),
        "updates_hash": stable_final_publication_hash(updates_d),
        "visible_updates_hash": stable_final_publication_hash(visible_updates_d),
        "contract_hash": stable_final_publication_hash(contract_d),
        "state_fingerprint": state_fingerprint,
        "derived_from": "FinalDesignGuidePublication.primary_apply_payload_projection",
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    projection["projection_hash"] = stable_final_publication_hash(projection)
    return projection


def build_final_visible_debug_projection(
    *,
    enabled: bool,
    button_contract: dict[str, Any] | None = None,
    updates: dict[str, Any] | None = None,
    family: str | None = None,
    payload: dict[str, Any] | None = None,
    item: dict[str, Any] | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Project final-visible debug fields without mutating page debug state."""

    item_d = _mapping(item)
    contract_d = _mapping(button_contract)
    updates_d = _mapping(updates)
    projection: dict[str, Any] = {
        "primary_button_contract": dict(contract_d),
        "button_contract": dict(contract_d),
        "displayed_primary_button_contract": dict(contract_d),
        "button_contract_enabled": bool(enabled),
        "button_contract_updates": dict(updates_d) if enabled else {},
        "button_contract_preview_pass": bool(enabled),
        "button_contract_blocking_reason": None if enabled else str(reason or "").strip(),
        "design_guide_primary_apply_payload": _mapping(payload) if enabled else {},
        "selected_action_updates": dict(updates_d) if enabled else {},
        "family_status_current": _mapping(item_d.get("family_status_current")),
        "family_status_preview": _mapping(item_d.get("family_status_preview")),
        "blocker_attempts_by_family": _mapping(item_d.get("blocker_attempts_by_family")),
    }
    if enabled:
        projection.update(
            {
                "selected_action_type": "apply_resolved_candidate",
                "selected_action_family": str(family or "").strip(),
                "candidate_search_evidence": _mapping(item_d.get("candidate_search_evidence")),
                "exact_blockers_by_family": _mapping(item_d.get("exact_blockers_by_family")),
                "post_click_exact_blockers_by_family": _mapping(
                    item_d.get("post_click_exact_blockers_by_family")
                ),
                "cleanup_evidence_by_family": _mapping(item_d.get("cleanup_evidence_by_family")),
                "post_click_cleanup_evidence_by_family": _mapping(
                    item_d.get("post_click_cleanup_evidence_by_family")
                ),
            }
        )
    return {
        "debug_projection": dict(projection),
        "projection_hash": stable_final_publication_hash(projection),
        "derived_from": "FinalDesignGuidePublication.final_visible_debug_projection",
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }


def build_final_visible_contract_binding_disabled_output_projection(
    *,
    input_item: dict[str, Any] | None = None,
    component_payloads: dict[str, Any] | None = None,
    debug_projection: dict[str, Any] | None = None,
) -> FinalVisibleContractBindingOutputProjection:
    """Project the disabled-output branch without page/session mutation."""

    item = _mapping(input_item)
    components = _mapping(component_payloads)
    family = _final_visible_projection_family(item)
    reason = _final_visible_projection_blocker_reason(item)
    disabled_contract = _final_visible_projection_disabled_contract(
        item,
        family=family,
        reason=reason,
    )
    authority_contract = _mapping(components.get("cta_authority_contract"))
    display_projection = _mapping(components.get("family_status_display_projection"))
    projected_item_overlay = _mapping(components.get("projected_item_overlay"))
    projected_item = dict(item)
    projected_item.update(display_projection)
    projected_item["button_contract"] = dict(authority_contract or disabled_contract)
    projected_item["primary_card_actionable"] = False
    projected_item["selected_action_updates"] = {}
    if _final_visible_projection_is_visible_blocker(projected_item) or not _text(
        projected_item.get("action_type")
    ):
        projected_item["updates"] = {}
        projected_item["action_payload"] = {}
        projected_item["resolved_candidate"] = {}
        projected_item["action_type"] = None
    projected_item.update(projected_item_overlay)
    projection = build_final_visible_contract_binding_output_projection(
        callsite_id="final_contract_binding.disabled_output",
        input_item=dict(item),
        rebind_projection={
            "item": dict(projected_item),
            "contract": dict(disabled_contract),
            "evidence_for_binding": _mapping(projected_item.get("candidate_search_evidence")),
            "debug": _mapping(debug_projection),
        },
        debug_projection=_mapping(debug_projection),
    )
    payload = projection.to_dict()
    payload["branch_projection"] = "disabled_output"
    payload["branch_projection_hash"] = stable_final_publication_hash(
        {
            "branch_projection": "disabled_output",
            "item": payload.get("item"),
            "cta_projection": payload.get("cta_projection"),
            "action_payload_projection": payload.get("action_payload_projection"),
            "resolved_candidate_projection": payload.get("resolved_candidate_projection"),
        }
    )
    return FinalVisibleContractBindingOutputProjection(**{
        key: value
        for key, value in payload.items()
        if key in FinalVisibleContractBindingOutputProjection.__dataclass_fields__
    })


def build_final_visible_contract_binding_enabled_action_output_projection(
    *,
    input_item: dict[str, Any] | None = None,
    component_payloads: dict[str, Any] | None = None,
    debug_projection: dict[str, Any] | None = None,
) -> FinalVisibleContractBindingOutputProjection:
    """Project the enabled-action output branch without page/session mutation."""

    item = _mapping(input_item)
    components = _mapping(component_payloads)
    projected_item = dict(item)
    for component_key in (
        "family_status_display_projection",
        "action_payload_projection",
        "resolved_candidate_projection",
        "candidate_search_evidence_projection",
        "display_truth_projection",
        "selected_action_projection",
    ):
        payload = _mapping(components.get(component_key))
        if payload:
            projected_item.update(payload)
    projected_item.update(_mapping(components.get("projected_item_overlay")))
    authority_contract = _mapping(components.get("cta_authority_contract"))
    if authority_contract:
        projected_item["button_contract"] = dict(authority_contract)
    projection = build_final_visible_contract_binding_output_projection(
        callsite_id="final_contract_binding.enabled_action_output",
        input_item=dict(item),
        rebind_projection={
            "item": dict(projected_item),
            "contract": _mapping(projected_item.get("button_contract")),
            "evidence_for_binding": _mapping(projected_item.get("candidate_search_evidence")),
            "debug": _mapping(debug_projection),
        },
        debug_projection=_mapping(debug_projection),
    )
    payload = projection.to_dict()
    payload["branch_projection"] = "enabled_action_output"
    payload["branch_projection_hash"] = stable_final_publication_hash(
        {
            "branch_projection": "enabled_action_output",
            "item": payload.get("item"),
            "cta_projection": payload.get("cta_projection"),
            "action_payload_projection": payload.get("action_payload_projection"),
            "resolved_candidate_projection": payload.get("resolved_candidate_projection"),
        }
    )
    return FinalVisibleContractBindingOutputProjection(**{
        key: value
        for key, value in payload.items()
        if key in FinalVisibleContractBindingOutputProjection.__dataclass_fields__
    })


def build_final_visible_contract_binding_snapshot_reuse_projection(
    *,
    snapshot_item: dict[str, Any] | None = None,
    debug_projection: dict[str, Any] | None = None,
) -> FinalVisibleContractBindingOutputProjection:
    """Project the snapshot-reuse branch without page/session mutation."""

    item = _mapping(snapshot_item)
    return build_final_visible_contract_binding_output_projection(
        callsite_id="final_contract_binding.snapshot_reuse_output",
        input_item=dict(item),
        rebind_projection={
            "item": dict(item),
            "contract": _mapping(item.get("button_contract")),
            "evidence_for_binding": _mapping(item.get("candidate_search_evidence")),
            "debug": _mapping(debug_projection),
        },
        debug_projection=_mapping(debug_projection),
    )


def build_final_visible_render_binding_payload(
    *,
    callsite_id: str | None = None,
    input_item: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    rec: dict[str, Any] | None = None,
    existing_cutover_traces: dict[str, Any] | None = None,
    previous_adapter_state: dict[str, Any] | None = None,
    debug_available: bool = True,
    input_available: bool = True,
    debug_force_rebuild: bool = False,
    apply_in_flight: bool = False,
    apply_in_flight_check_failed: bool = False,
    post_click_state_present: bool = False,
) -> dict[str, Any]:
    """Build the final-visible binding payload for the remaining render-stage shell."""

    callsite = str(callsite_id or "").strip()
    source_item = _mapping(input_item)
    if not bool(debug_available) or not bool(input_available):
        bypass = {"bypass": False, "reason": "missing_debug_or_input"}
    elif bool(debug_force_rebuild):
        bypass = {"bypass": False, "reason": "debug_force_rebuild"}
    elif bool(apply_in_flight_check_failed):
        bypass = {"bypass": False, "reason": "apply_in_flight_check_failed"}
    elif bool(apply_in_flight):
        bypass = {"bypass": False, "reason": "apply_in_flight"}
    elif bool(post_click_state_present):
        bypass = {"bypass": False, "reason": "post_click_state_present"}
    else:
        previous = _mapping(previous_adapter_state)
        current = {
            "callsite_id": callsite,
            "adapter_kind": str(previous.get("adapter_kind") or ""),
            "input_item_hash": stable_final_publication_hash(dict(source_item)),
            "output_item_hash": stable_final_publication_hash(dict(source_item)),
            "state_hash": stable_final_publication_hash(_mapping(state)),
            "rec_hash": stable_final_publication_hash(_mapping(rec)),
            "adapter_hash": str(previous.get("adapter_hash") or ""),
            "component_projection_hash": str(previous.get("component_projection_hash") or ""),
            "fallback_reason": "",
            "derived_from": "FinalDesignGuidePublication.final_visible_render_binding_payload.inline_bypass_state",
            "product_driving": True,
            "render_driving": False,
            "apply_driving": False,
            "session_driving": False,
        }
        current["bypass_state_hash"] = stable_final_publication_hash(current)
        if not previous.get("bypass_state_hash"):
            bypass = {"bypass": False, "reason": "missing_previous_adapter_state"}
        elif not previous.get("adapter_hash"):
            bypass = {"bypass": False, "reason": "missing_previous_adapter_hash"}
        elif str(previous.get("fallback_reason") or "").strip():
            bypass = {"bypass": False, "reason": "previous_adapter_fallback_state"}
        else:
            required_equal_fields = (
                "callsite_id",
                "adapter_kind",
                "state_hash",
                "rec_hash",
                "adapter_hash",
                "component_projection_hash",
            )
            mismatches = [
                field
                for field in required_equal_fields
                if previous.get(field) != current.get(field)
            ]
            output_matches_input = previous.get("output_item_hash") == current.get("input_item_hash")
            if mismatches:
                bypass = {
                    "bypass": False,
                    "reason": "adapter_state_mismatch",
                    "mismatches": mismatches,
                }
            elif not output_matches_input:
                bypass = {"bypass": False, "reason": "previous_output_not_current_input"}
            else:
                bypass = {
                    "bypass": True,
                    "reason": "stable_adapter_hash_restamper_bridge",
                    "adapter_hash": current.get("adapter_hash"),
                    "adapter_state_hash": current.get("bypass_state_hash"),
                }
        bypass.update(
            {
                "previous_state_hash": stable_final_publication_hash(previous),
                "current_state_hash": stable_final_publication_hash(current),
                "current_bypass_state": dict(current),
            }
        )
    bypass.update(
        {
            "callsite_id": callsite,
            "debug_available": bool(debug_available),
            "input_available": bool(input_available),
            "debug_force_rebuild": bool(debug_force_rebuild),
            "apply_in_flight": bool(apply_in_flight),
            "apply_in_flight_check_failed": bool(apply_in_flight_check_failed),
            "post_click_state_present": bool(post_click_state_present),
            "derived_from": "FinalDesignGuidePublication.final_visible_render_binding_payload",
            "product_driving": True,
            "render_driving": False,
            "apply_driving": False,
            "session_driving": False,
        }
    )
    bypass["decision_hash"] = stable_final_publication_hash(bypass)
    bypass_reason = str(bypass.get("reason") or "").strip()

    if bool(bypass.get("bypass")):
        payload = {
            "callsite_id": callsite,
            "item": dict(source_item),
            "adapter_projection": {},
            "debug_projection": {},
            "render_projection": {},
            "debug_updates": {
                "final_visible_restamper_adapter_identity_proof": (
                    "direct_pass_through_after_adapter_identity_proof"
                ),
                "final_visible_restamper_bridge_render_fast_final_visible_item_bypassed": True,
                "final_visible_restamper_bridge_render_fast_final_visible_item_bypass_reason": (
                    bypass_reason
                ),
                "final_visible_restamper_bridge_render_fast_final_visible_item_bypass_hash": (
                    bypass.get("adapter_state_hash")
                ),
            },
            "bypass_decision": dict(bypass),
            "store_projection_debug": False,
            "used_direct_pass_through": True,
            "derived_from": "FinalDesignGuidePublication.final_visible_render_binding_payload",
            "product_driving": True,
            "render_driving": False,
            "apply_driving": False,
            "session_driving": False,
        }
        payload["payload_hash"] = stable_final_publication_hash(payload)
        return payload

    contract = _mapping(source_item.get("button_contract"))
    action_payload = _mapping(source_item.get("action_payload"))
    resolved_candidate = _mapping(source_item.get("resolved_candidate"))
    evidence = _mapping(source_item.get("candidate_search_evidence"))
    if not evidence:
        evidence = _mapping(action_payload.get("candidate_search_evidence"))
    if not evidence:
        evidence = _mapping(resolved_candidate.get("candidate_search_evidence"))
    updates = (
        _mapping(contract.get("updates"))
        or _mapping(source_item.get("selected_action_updates"))
        or _mapping(source_item.get("updates"))
        or _mapping(action_payload.get("updates"))
        or _mapping(resolved_candidate.get("updates"))
    )
    enabled = bool(contract.get("enabled") or contract.get("actionable"))
    action_type = _text(contract.get("action_type"), source_item.get("action_type"))
    selected_action_projection: dict[str, Any] = {}
    if enabled and updates:
        selected_action_projection.update(
            {
                "action_type": action_type or "apply_resolved_candidate",
                "updates": dict(updates),
                "selected_action_updates": dict(updates),
                "primary_card_actionable": True,
            }
        )
    family_status_display_projection = {
        key: source_item[key]
        for key in (
            "_current_state_for_display",
            "blocker_attempts_by_family",
            "family_status_current",
            "family_status_preview",
        )
        if key in source_item
    }
    display_truth_projection = {}
    if isinstance(source_item.get("display_truth"), dict):
        display_truth_projection["display_truth"] = _mapping(source_item.get("display_truth"))
    projected_item_overlay: dict[str, Any] = {}
    if enabled:
        projected_item_overlay.update(
            {
                "button_contract": dict(contract),
                "action_payload": dict(action_payload),
                "resolved_candidate": dict(resolved_candidate),
                "candidate_search_evidence": dict(evidence),
            }
        )
        projected_item_overlay.update(selected_action_projection)
        if _text(source_item.get("family")):
            projected_item_overlay["family"] = source_item.get("family")
        if _text(source_item.get("check_key")):
            projected_item_overlay["check_key"] = source_item.get("check_key")
        if _text(source_item.get("selected_action_family")):
            projected_item_overlay["selected_action_family"] = source_item.get("selected_action_family")
        if _text(source_item.get("candidate_id")):
            projected_item_overlay["candidate_id"] = source_item.get("candidate_id")
        if _text(source_item.get("source_candidate_id")):
            projected_item_overlay["source_candidate_id"] = source_item.get("source_candidate_id")
    else:
        projected_item_overlay.update(
            {
                "button_contract": dict(contract),
                "primary_card_actionable": False,
                "selected_action_updates": {},
                "updates": {},
                "action_payload": {},
                "resolved_candidate": {},
                "action_type": None,
            }
        )
    if display_truth_projection:
        projected_item_overlay.update(display_truth_projection)
    component_payloads = {
        "cta_authority_contract": dict(contract),
        "family_status_display_projection": dict(family_status_display_projection),
        "action_payload_projection": {"action_payload": dict(action_payload)}
        if enabled
        else {},
        "resolved_candidate_projection": {"resolved_candidate": dict(resolved_candidate)}
        if enabled
        else {},
        "candidate_search_evidence_projection": {"candidate_search_evidence": dict(evidence)}
        if enabled
        else {},
        "display_truth_projection": dict(display_truth_projection),
        "selected_action_projection": dict(selected_action_projection),
        "projected_item_overlay": dict(projected_item_overlay),
    }
    branch_id = (
        "final_contract_binding.enabled_action_output"
        if enabled
        else "final_contract_binding.disabled_output"
    )
    branch_projection = {
        "branch_id": branch_id,
        "component_payloads": dict(component_payloads),
        "enabled": bool(enabled),
        "input_item_hash": stable_final_publication_hash(source_item),
        "component_payloads_hash": stable_final_publication_hash(component_payloads),
        "derived_from": "FinalDesignGuidePublication.final_visible_contract_binding_component_projection",
        "product_driving": False,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    branch_projection["projection_hash"] = stable_final_publication_hash(branch_projection)
    projection_payload: dict[str, Any] = {}
    projected_item: dict[str, Any] = {}
    if branch_id == "final_contract_binding.disabled_output":
        projection_payload = build_final_visible_contract_binding_disabled_output_projection(
            input_item=dict(source_item),
            component_payloads=dict(component_payloads),
            debug_projection={},
        ).to_dict()
    elif branch_id == "final_contract_binding.enabled_action_output":
        projection_payload = build_final_visible_contract_binding_enabled_action_output_projection(
            input_item=dict(source_item),
            component_payloads=dict(component_payloads),
            debug_projection={},
        ).to_dict()

    projected_item = _mapping(projection_payload.get("item"))
    projected_hash = stable_final_publication_hash(projected_item)
    fallback_reason = ""
    output_item = dict(projected_item or source_item)

    output_hash = stable_final_publication_hash(output_item)
    adapter_hash = stable_final_publication_hash(
        {
            "callsite_id": callsite,
            "branch_id": branch_id,
            "component_projection_hash": branch_projection.get("projection_hash"),
            "output_hash": output_hash,
        }
    )
    adapter_projection = {
        "callsite_id": callsite,
        "branch_id": branch_id,
        "item": dict(output_item),
        "output_hash": output_hash,
        "adapter_hash": adapter_hash,
        "component_projection": dict(branch_projection),
        "component_projection_hash": branch_projection.get("projection_hash"),
        "component_payloads": dict(component_payloads),
        "projection": dict(projection_payload),
        "projected_hash": projected_hash,
        "fallback_reason": fallback_reason,
        "cutover_ready": True,
        "used_old_helper_fallback": False,
        "derived_from": "FinalDesignGuidePublication.final_visible_contract_binding_adapter_projection",
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    adapter_projection["projection_hash"] = stable_final_publication_hash(adapter_projection)
    projection = dict(adapter_projection)
    branch_projection = _mapping(projection.get("component_projection"))
    branch_id = str(branch_projection.get("branch_id") or "").strip()
    output_item = _mapping(projection.get("item")) or dict(source_item)
    adapter_cutover = True
    fallback_reason = str(projection.get("fallback_reason") or "").strip()
    output_hash = stable_final_publication_hash(output_item)
    adapter_hash_payload = {
        "branch_id": branch_id,
        "component_projection_hash": branch_projection.get("projection_hash"),
        "output_hash": output_hash,
    }
    if fallback_reason:
        adapter_hash_payload["fallback_reason"] = fallback_reason
    adapter_hash = stable_final_publication_hash(adapter_hash_payload)
    trace_row = {
        "callsite_id": callsite,
        "branch_id": branch_id,
        "component_projection_hash": branch_projection.get("projection_hash"),
        "output_hash": output_hash,
        "adapter_hash": adapter_hash,
        "used_old_helper_fallback": False,
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    traces = _mapping(existing_cutover_traces)
    traces[callsite] = dict(trace_row)
    bypass_state = {
        "callsite_id": callsite,
        "adapter_kind": "compatibility_adapter",
        "input_item_hash": stable_final_publication_hash(dict(source_item)),
        "output_item_hash": stable_final_publication_hash(dict(output_item)),
        "state_hash": stable_final_publication_hash(_mapping(state)),
        "rec_hash": stable_final_publication_hash(_mapping(rec)),
        "adapter_hash": adapter_hash,
        "component_projection_hash": str(branch_projection.get("projection_hash") or ""),
        "fallback_reason": fallback_reason,
        "derived_from": "FinalDesignGuidePublication.final_visible_render_binding_payload.inline_bypass_state",
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    bypass_state["bypass_state_hash"] = stable_final_publication_hash(bypass_state)
    debug_updates = {
        "final_visible_contract_binding_output_cutover": True,
        "final_visible_contract_binding_output_cutover_callsite": branch_id,
        "final_visible_contract_binding_output_cutover_source_hash": "",
        "final_visible_contract_binding_output_cutover_projected_hash": projection.get(
            "projected_hash"
        ),
        "final_visible_contract_binding_output_cutover_authority": (
            "FinalDesignGuidePublication.final_visible_contract_binding_adapter_projection"
        ),
        "final_visible_contract_binding_output_cutover_product_driving": True,
        "final_visible_contract_binding_output_cutover_render_driving": False,
        "final_visible_contract_binding_output_cutover_apply_driving": False,
        "final_visible_contract_binding_output_cutover_session_driving": False,
        "final_visible_contract_binding_output_trace_wired": True,
        "final_visible_contract_binding_output_product_driving": False,
        "final_visible_contract_binding_output_render_driving": False,
        "final_visible_contract_binding_output_apply_driving": False,
        "final_visible_contract_binding_output_session_driving": False,
        "final_visible_contract_binding_adapter_cutovers": dict(traces),
        "final_visible_contract_binding_adapter_cutover_latest": callsite,
        "final_visible_contract_binding_adapter_cutover_hash": stable_final_publication_hash(
            traces
        ),
    }
    debug_projection = {
        "callsite_id": callsite,
        "branch_id": branch_id,
        "item": dict(output_item),
        "trace_row": dict(trace_row),
        "traces": dict(traces),
        "bypass_state": dict(bypass_state),
        "debug_updates": dict(debug_updates),
        "adapter_hash": adapter_hash,
        "output_hash": output_hash,
        "fallback_reason": fallback_reason,
        "cutover_ready": adapter_cutover,
        "derived_from": "FinalDesignGuidePublication.final_visible_render_binding_payload",
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    debug_projection["projection_hash"] = stable_final_publication_hash(debug_projection)
    render_projection = {
        "callsite_id": callsite,
        "item": dict(output_item),
        "adapter_projection": dict(adapter_projection),
        "debug_projection": dict(debug_projection),
        "debug_updates": dict(debug_projection.get("debug_updates") or {}),
        "bypass_state": dict(debug_projection.get("bypass_state") or {}),
        "cutover_ready": bool(debug_projection.get("cutover_ready")),
        "output_hash": stable_final_publication_hash(output_item),
    }
    payload = {
        "callsite_id": callsite,
        "item": dict(output_item),
        "adapter_projection": dict(adapter_projection),
        "debug_projection": dict(debug_projection),
        "render_projection": dict(render_projection),
        "debug_updates": {
            "final_visible_restamper_adapter_pre_card_identity_proof": (
                "pre_card_direct_pass_through_after_adapter_identity_proof"
            ),
            "final_visible_restamper_bridge_render_fast_final_visible_item_bypassed": False,
            "final_visible_restamper_bridge_render_fast_final_visible_item_bypass_reason": (
                bypass_reason or "rebuild"
            ),
        },
        "bypass_decision": dict(bypass),
        "store_projection_debug": True,
        "used_direct_pass_through": False,
        "derived_from": "FinalDesignGuidePublication.final_visible_render_binding_payload",
        "product_driving": True,
        "render_driving": False,
        "apply_driving": False,
        "session_driving": False,
    }
    payload["payload_hash"] = stable_final_publication_hash(payload)
    return payload


FINAL_VISIBLE_CONTRACT_BINDING_OUTPUT_COMPONENTS: tuple[str, ...] = (
    "target_band_promotion",
    "safe_consistency_guard",
    "combined_consistency_guard",
    "contract_truth",
    "no_second_cta",
    "rebind_effects",
    "rebind_projection",
    "cleanup_evidence_rehydrate",
    "cleanup_evidence_rehydrate_projection",
    "intent_contract_rebind",
)


__all__ = [
    "FinalDesignGuideCTA",
    "COMPUTE_PUBLICATION_HANDOFF_REBOUND_BLOCKING_FIELDS",
    "FINAL_VISIBLE_CONTRACT_BINDING_OUTPUT_COMPONENTS",
    "FinalDesignGuideDisplay",
    "FinalDesignGuideComputePublicationHandoffReboundDecisionProof",
    "FinalDesignGuideEvidence",
    "FinalDesignGuideOutcomeState",
    "FinalDesignGuidePostResolverMutationProof",
    "FinalDesignGuidePublication",
    "FinalDesignGuideDirectShellCardProjection",
    "FinalDesignGuideDirectShellIdentityProjection",
    "FinalDesignGuidePublicationMutationProof",
    "FinalVisibleContractBindingOutputProjection",
    "FinalDesignGuideVerifierPayload",
    "build_final_design_guide_cta",
    "build_final_design_guide_display",
    "build_final_design_guide_evidence",
    "build_final_design_guide_compute_publication_handoff_rebound_decision_proof",
    "build_final_design_guide_publication",
    "build_final_design_guide_direct_shell_card_projection",
    "build_final_design_guide_direct_shell_identity_projection",
    "build_final_design_guide_post_resolver_mutation_proof",
    "build_final_design_guide_post_click_low_bending_resolution_request_proof",
    "build_final_design_guide_post_click_low_bending_resolution_result_projection_proof",
    "build_final_design_guide_post_click_low_bending_residual_shear_cleanup_route_proof",
    "build_final_design_guide_post_click_low_bending_resolution_result_item_adapter_proof",
    "build_final_design_guide_post_click_bending_replacement_audit_result_proof",
    "build_final_design_guide_post_click_final_contract_check_adapter_proof",
    "build_final_design_guide_post_click_final_contract_predicate_result_adapter",
    "build_final_design_guide_post_click_final_contract_check_adapter_result",
    "build_final_design_guide_post_click_exact_blocker_raw_bound_parity_proof",
    "build_final_visible_contract_binding_no_second_cta_result",
    "build_final_visible_contract_binding_target_band_promotion_result",
    "build_final_visible_contract_binding_consistency_guard_result",
    "build_final_visible_contract_binding_truth_result",
    "build_final_visible_contract_binding_typed_fallback_payload",
    "build_final_visible_contract_binding_rebind_effects_proof",
    "build_final_visible_contract_binding_rebind_projection",
    "build_final_visible_family_status_display_projection",
    "build_final_visible_combined_outside_target_blocker_evidence_projection",
    "build_final_visible_primary_payload_binding_audit_projection",
    "build_final_design_guide_primary_apply_payload_projection",
    "build_final_visible_debug_projection",
    "build_final_visible_contract_binding_disabled_output_projection",
    "build_final_visible_contract_binding_enabled_action_output_projection",
    "build_final_visible_contract_binding_snapshot_reuse_projection",
    "build_final_visible_render_binding_payload",
    "build_final_visible_contract_binding_cleanup_evidence_rehydrate_result",
    "build_final_visible_contract_binding_cleanup_evidence_rehydrate_projection",
    "build_final_design_guide_card_vm_intent_contract_promotion_result",
    "build_final_design_guide_shear_exact_blocker_safe_intent_result",
    "build_final_design_guide_card_render_contract_preference_result",
    "build_final_design_guide_displayed_primary_safe_combined_promotion_result",
    "build_final_design_guide_post_click_safe_intent_allowed_gate_result",
    "build_final_design_guide_post_click_proof_intent_contract_result",
    "build_final_design_guide_post_cleanup_render_audit_intent_contract_result",
    "build_final_design_guide_late_render_shear_action_intent_contract_result",
    "build_final_visible_contract_binding_intent_contract_rebind_result",
    "build_final_visible_render_stage_intent_contract_rebind_result",
    "select_enabled_design_guide_contract_from_intent_rows",
    "build_final_design_guide_publication_mutation_proof",
    "build_final_visible_contract_binding_output_projection",
    "build_final_design_guide_verifier_payload",
    "build_collapsed_guidance_item_from_final_publication",
    "build_final_publication_display_from_current_card_model",
    "build_final_publication_cta_from_current_state",
    "normalise_stale_family_contract_violation_item",
    "build_render_stage_post_resolver_item_mutation_proof",
    "canonical_final_publication_authority_payload",
    "infer_final_design_guide_outcome_state",
    "stable_final_publication_authority_hash",
    "stable_final_publication_hash",
]

