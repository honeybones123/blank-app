"""Guidance item family consolidation for the Inputs Design Guide."""

from __future__ import annotations

from typing import Any

from inputs_page_modules.design_guide import _candidate_cache_key
from inputs_page_modules.design_guide.item_identity import _guidance_item_family


_GUIDANCE_ITEM_CONSOLIDATION_DEPENDENCIES: tuple[str, ...] = ()


def bind_guidance_item_consolidation_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _GUIDANCE_ITEM_CONSOLIDATION_DEPENDENCIES
            if name in namespace
        }
    )


def _design_guide_button_contract_enabled(contract: dict | None) -> bool:
    value = contract if isinstance(contract, dict) else {}
    return bool(
        value.get("actionable")
        and dict(value.get("updates") or {})
        and bool(value.get("preview_pass"))
        and value.get("blocking_reason") is None
    )


def _first_actionable_guidance_item(
    guidance_items: list[dict] | None,
) -> dict | None:
    for item in guidance_items or []:
        if not isinstance(item, dict) or not str(
            item.get("action_type") or ""
        ).strip():
            continue
        contract = item.get("button_contract")
        if isinstance(contract, dict) and not _design_guide_button_contract_enabled(
            contract
        ):
            continue
        return item
    return None


def _guidance_update_map(item: dict | None) -> dict:
    if not isinstance(item, dict):
        return {}
    payload = dict(item.get("action_payload") or {})
    return dict(
        payload.get("updates")
        or payload.get("resolved_candidate_updates")
        or {}
    )


def _guidance_item_coverage_tuple(item: dict | None) -> tuple:
    if not isinstance(item, dict):
        return (0, 0, 0, 0)
    payload = dict(item.get("action_payload") or {})
    failure_coverage = dict(
        item.get("failure_coverage")
        or payload.get("failure_coverage")
        or {}
    )
    covered = list(
        item.get("covered_fail_keys")
        or payload.get("covered_fail_keys")
        or failure_coverage.get("covered_fail_keys")
        or []
    )
    remaining = list(
        item.get("remaining_fail_keys")
        or payload.get("remaining_fail_keys")
        or failure_coverage.get("remaining_fail_keys")
        or []
    )
    covers_all = bool(
        item.get("covers_all_current_failures")
        or payload.get("covers_all_current_failures")
        or failure_coverage.get("covers_all_current_failures")
    )
    family = _guidance_item_family(item)
    family_rank = {
        "combined": 3,
        "bending": 2,
        "shear": 1,
        "other": 0,
        "unknown": 0,
    }.get(family, 0)
    return (
        1 if covers_all else 0,
        len(covered),
        -len(remaining),
        family_rank,
    )


def _guidance_items_materially_overlap(
    first: dict | None,
    second: dict | None,
) -> bool:
    first_updates = _guidance_update_map(first)
    second_updates = _guidance_update_map(second)
    if not first_updates or not second_updates:
        return False
    if first_updates == second_updates:
        return True

    first_keys = set(first_updates)
    second_keys = set(second_updates)

    def _subset_same_values(smaller: dict, larger: dict) -> bool:
        for key, value in smaller.items():
            if key not in larger or larger.get(key) != value:
                return False
        return True

    if first_keys.issubset(second_keys) and _subset_same_values(
        first_updates,
        second_updates,
    ):
        return True
    if second_keys.issubset(first_keys) and _subset_same_values(
        second_updates,
        first_updates,
    ):
        return True
    return False


def _guidance_item_is_same_problem_wrapper(primary: dict | None, secondary: dict | None) -> bool:
    """
    True when the secondary card is not a genuinely different next action, but only a narrower
    or broader wrapper around the same engineering move/problem already represented by primary.
    """
    if not isinstance(primary, dict) or not isinstance(secondary, dict):
        return False

    primary_updates = _guidance_update_map(primary)
    secondary_updates = _guidance_update_map(secondary)
    if not primary_updates or not secondary_updates:
        return False

    if _guidance_items_materially_overlap(primary, secondary):
        return True

    primary_family = _guidance_item_family(primary)
    secondary_family = _guidance_item_family(secondary)

    primary_cov = _guidance_item_coverage_tuple(primary)
    secondary_cov = _guidance_item_coverage_tuple(secondary)

    primary_reason = str(
        primary.get("why") or primary.get("subtitle") or primary.get("reasoning") or ""
    ).strip().lower()
    secondary_reason = str(
        secondary.get("why") or secondary.get("subtitle") or secondary.get("reasoning") or ""
    ).strip().lower()
    primary_title = str(primary.get("title_main") or primary.get("canonical_winner_label") or "").strip().lower()
    secondary_title = str(secondary.get("title_main") or secondary.get("canonical_winner_label") or "").strip().lower()

    primary_governing = str(
        primary.get("governing_check") or primary.get("governing_label") or ""
    ).strip().lower()
    secondary_governing = str(
        secondary.get("governing_check") or secondary.get("governing_label") or ""
    ).strip().lower()

    # Efficiency / overdesign: geometry tightening and shear tightening are independent moves.
    # Empty governing labels otherwise satisfy `primary_governing == secondary_governing` and
    # incorrectly suppress a valid shear secondary behind a geometry primary (presentation only).
    _eff_geom_primary_actions = frozenset(
        {
            "tighten_geometry",
            "apply_geometry_recommendation",
            "increase_depth",
            "increase_width",
        },
    )
    _eff_shear_update_keys = frozenset({"lig_d", "lig_legs", "s_lig"})
    if (
        str(primary.get("status") or "") == "EFFICIENCY"
        and str(secondary.get("status") or "") == "EFFICIENCY"
        and primary_family in {"bending", "combined"}
        and secondary_family == "shear"
        and str(primary.get("action_type") or "") in _eff_geom_primary_actions
    ):
        sk = set(secondary_updates.keys())
        if sk and sk <= _eff_shear_update_keys:
            return False

    if primary_family in {"bending", "combined"} and secondary_family == "shear":
        if secondary_cov <= primary_cov:
            if primary_governing == secondary_governing or "shear" in secondary_governing:
                return True
            if secondary_reason and primary_reason and secondary_reason in primary_reason:
                return True
            if "shear" in secondary_title and (
                "depth" in primary_title or "width" in primary_title or "reinforcement" in primary_title
            ):
                return True

    if primary_family == "shear" and secondary_family in {"bending", "combined"}:
        if secondary_cov <= primary_cov:
            if primary_governing == secondary_governing or "shear" in primary_governing:
                return True

    return False


def _collapse_to_single_primary_guidance_item(
    guidance_items: list[dict],
    state: dict,
) -> tuple[list[dict], dict]:
    """
    If the primary actionable item is a resolved compound candidate that covers
    all current failing checks, show only that primary card.
    """
    items = list(guidance_items or [])
    if not items:
        return items, {
            "collapsed": False,
            "reason": "no_items",
        }

    primary = _first_actionable_guidance_item(items)
    if not isinstance(primary, dict):
        return items, {
            "collapsed": False,
            "reason": "no_actionable_primary",
        }

    payload = dict(primary.get("action_payload") or {})
    failure_cov = dict(payload.get("failure_coverage") or {})
    subfamilies = list(
        primary.get("subfamilies")
        or primary.get("resolved_candidate_subfamilies")
        or payload.get("resolved_candidate_subfamilies")
        or []
    )

    is_resolved_candidate = str(primary.get("action_type") or "") == "apply_resolved_candidate"
    covers_all = bool(
        primary.get("covers_all_current_failures")
        or failure_cov.get("covers_all_current_failures")
    )
    is_multi_family = len(set(str(x) for x in subfamilies if str(x).strip())) >= 2

    if is_resolved_candidate and covers_all and is_multi_family:
        return [primary], {
            "collapsed": True,
            "reason": "primary_compound_candidate_covers_all_failures",
            "covered_fail_keys": list(failure_cov.get("covered_fail_keys") or []),
            "remaining_fail_keys": list(failure_cov.get("remaining_fail_keys") or []),
            "subfamilies": list(subfamilies),
            "compound_shear_augmented": bool(
                primary.get("compound_shear_augmented")
                or payload.get("compound_shear_augmented"),
            ),
            "state_fp": _candidate_cache_key(dict(state or {})),
        }

    return items, {
        "collapsed": False,
        "reason": "primary_not_comprehensive_compound_candidate",
        "covered_fail_keys": list(failure_cov.get("covered_fail_keys") or []),
        "remaining_fail_keys": list(failure_cov.get("remaining_fail_keys") or []),
        "subfamilies": list(subfamilies),
        "compound_shear_augmented": bool(
            primary.get("compound_shear_augmented")
            or payload.get("compound_shear_augmented"),
        ),
        "state_fp": _candidate_cache_key(dict(state or {})),
    }


def _consolidate_guidance_items_by_family(
    guidance_items: list[dict],
) -> tuple[list[dict], dict]:
    items = list(guidance_items or [])
    if not items:
        return items, {
            "applied": False,
            "reason": "no_items",
            "primary_family": "unknown",
            "secondary_families": [],
            "promoted_title": None,
            "suppressed_titles": [],
        }

    def _is_actionable(item: dict | None) -> bool:
        return bool(isinstance(item, dict) and item.get("action_type"))

    primary = items[0]
    primary_family = _guidance_item_family(primary)
    promoted_title = None
    displaced_primary = None
    if _is_actionable(primary) and primary_family == "shear":
        primary_cov = _guidance_item_coverage_tuple(primary)
        best_idx = 0
        best_item = primary
        for idx, item in enumerate(items[1:], start=1):
            fam = _guidance_item_family(item)
            if not _is_actionable(item):
                continue
            if fam not in {"bending", "combined"}:
                continue
            cov = _guidance_item_coverage_tuple(item)
            if cov > primary_cov:
                primary_cov = cov
                best_idx = idx
                best_item = item
        if best_idx > 0:
            promoted_title = str(best_item.get("title_main") or "") or None
            displaced_primary = primary
            primary = best_item
            primary_family = _guidance_item_family(primary)
            reordered = [primary]
            if displaced_primary is not None:
                reordered.append(displaced_primary)
            reordered.extend(
                item
                for idx, item in enumerate(items)
                if idx != best_idx and item is not displaced_primary
            )
            items = reordered

    primary_actionable = _is_actionable(primary)
    kept = [primary]
    suppressed_titles: list[str] = []
    kept_secondary_titles: list[str] = []
    suppression_reason = "none"
    item_debug: list[dict] = []
    for item in items[1:]:
        fam = _guidance_item_family(item)
        candidate_cov = _guidance_item_coverage_tuple(item)
        primary_cov = _guidance_item_coverage_tuple(primary)
        materially_overlap = _guidance_items_materially_overlap(primary, item)
        same_problem_wrapper = _guidance_item_is_same_problem_wrapper(primary, item)
        suppress = False
        if primary_actionable and _is_actionable(item):
            if materially_overlap:
                suppress = True
                suppression_reason = "family_overlap_with_primary"
            elif same_problem_wrapper:
                suppress = True
                suppression_reason = "same_problem_wrapper"
            elif fam == primary_family and fam in {"shear", "bending", "combined"}:
                if candidate_cov <= primary_cov:
                    suppress = True
                    suppression_reason = "same_family_no_coverage_gain"
        item_debug.append(
            {
                "primary_family": primary_family,
                "candidate_family": fam,
                "primary_coverage": primary_cov,
                "candidate_coverage": candidate_cov,
                "materially_overlap": bool(materially_overlap),
                "same_problem_wrapper": bool(same_problem_wrapper),
                "suppressed": bool(suppress),
                "suppression_reason": suppression_reason if suppress else "kept_distinct_secondary",
                "title": str(item.get("title_main") or ""),
            },
        )
        if suppress:
            suppressed_titles.append(str(item.get("title_main") or ""))
            continue
        kept.append(item)
        kept_secondary_titles.append(str(item.get("title_main") or ""))

    return kept, {
        "applied": bool(promoted_title or suppressed_titles),
        "reason": (
            "promoted_later_better_primary"
            if promoted_title
            else suppression_reason
        ),
        "primary_family": primary_family,
        "secondary_families": [_guidance_item_family(item) for item in kept[1:]],
        "promoted_title": promoted_title,
        "suppressed_titles": suppressed_titles,
        "kept_secondary_titles": kept_secondary_titles,
        "item_debug": item_debug,
    }
