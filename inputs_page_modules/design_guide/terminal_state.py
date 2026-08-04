"""Design Guide terminal-state derivation helpers."""

from __future__ import annotations

from typing import Any

from inputs_application.engineering_predicates import parse_util_value as _parse_util_value
from inputs_page_modules.design_guide import _candidate_cache_key


_TERMINAL_STATE_DEPENDENCIES: tuple[str, ...] = ()


def bind_terminal_state_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _TERMINAL_STATE_DEPENDENCIES
            if name in namespace
        }
    )


def _design_guide_button_contract_enabled(contract: dict | None) -> bool:
    c = contract if isinstance(contract, dict) else {}
    return bool(
        c.get("actionable")
        and dict(c.get("updates") or {})
        and bool(c.get("preview_pass"))
        and c.get("blocking_reason") is None
    )


def _first_actionable_guidance_item(
    guidance_items: list[dict] | None,
) -> dict | None:
    """First item with a non-empty and enabled action contract."""
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


def _efficiency_terminal_proof_present(efficiency_state: dict) -> bool:
    """Return true only when the low-utilisation cleanup search is resolved."""
    if bool(efficiency_state.get("terminal_state_blocked")):
        return False
    exhaustion = efficiency_state.get("exhaustion_map")
    if not isinstance(exhaustion, dict) or not exhaustion:
        return False
    for record in exhaustion.values():
        if not isinstance(record, dict) or not bool(record.get("tried")):
            return False
        if not bool(record.get("accepted")) and not record.get("rejected_reason"):
            return False
    return True


def _family_exact_stop_terminal_proof_present(
    guidance_items: list[dict] | None,
    guidance_debug: dict | None,
) -> bool:
    """Recognise the family ladder's explicit no-action terminal proof."""

    sources = [
        *(row for row in list(guidance_items or []) if isinstance(row, dict)),
        dict(guidance_debug or {}),
    ]
    for source in sources:
        proof = dict(source.get("exact_stop_proof") or {})
        if not bool(
            source.get("family_ladder_terminal_exact_stop")
            or source.get("exact_stop_proven")
            or proof.get("current_state_terminal_exact_stop")
        ):
            continue
        if str(
            proof.get("terminal_candidate_status") or ""
        ).strip().upper() != "TERMINAL_EXACT_STOP":
            continue
        if proof.get("no_progressing_family_owned_candidate") is not True:
            continue
        return True
    return False


def _design_guide_terminal_state_from_render_artifacts(
    guidance_items: list[dict],
    guidance_debug: dict | None,
) -> str | None:
    dbg = dict(guidance_debug or {})
    eff = dict(dbg.get("efficiency_tightening_state") or {})
    eff_cls = str(eff.get("classification") or "").strip()
    actionable_item = _first_actionable_guidance_item(guidance_items)
    terminal_proven = bool(
        _efficiency_terminal_proof_present(eff)
        or _family_exact_stop_terminal_proof_present(
            guidance_items,
            dbg,
        )
    )

    if eff_cls == "optimal" and actionable_item is None and terminal_proven:
        return "optimal"
    if eff_cls == "very_low_demand" and actionable_item is None and terminal_proven:
        return "very_low_demand"

    top = guidance_items[0] if guidance_items else {}
    top_term = str((top or {}).get("design_guide_terminal_state") or "").strip()
    if top_term in {"optimal", "very_low_demand"} and terminal_proven:
        return top_term

    guidance_branch = str(dbg.get("guidance_branch") or "").strip()
    if guidance_branch in {"optimal", "very_low_demand"} and terminal_proven:
        return guidance_branch
    return None


def _derive_design_guide_terminal_state_from_current_overview(
    guidance_debug: dict,
    guidance_disp_state: dict,
    guidance_items: list[dict],
) -> str | None:
    dbg = dict(guidance_debug or {})
    existing = _design_guide_terminal_state_from_render_artifacts(guidance_items, dbg)
    ov = dict(dbg.get("overview") or {})
    statuses = dict(ov.get("statuses") or {})
    utils = dict(ov.get("utils") or {})
    fail_keys = [
        str(key)
        for key, value in statuses.items()
        if str(value or "").strip().upper() == "FAIL"
    ]
    numeric_utils = [
        util for util in (_parse_util_value(value) for value in utils.values())
        if util is not None and util > 0.0
    ]
    gov_util = next(
        (
            util for util in (
                _parse_util_value(ov.get("governing_util")),
                _parse_util_value(ov.get("worst_util")),
                _parse_util_value(dbg.get("current_util")),
                max(numeric_utils) if numeric_utils else None,
            )
            if util is not None and util > 0.0
        ),
        None,
    )
    eff = dict(dbg.get("efficiency_tightening_state") or {})
    terminal_proven = bool(
        _efficiency_terminal_proof_present(eff)
        or _family_exact_stop_terminal_proof_present(
            guidance_items,
            dbg,
        )
    )
    target_lo = _parse_util_value(eff.get("target_band_lo"))
    target_hi = _parse_util_value(eff.get("target_band_hi"))
    if target_lo is None:
        target_lo = 0.82
    if target_hi is None:
        target_hi = 0.92
    actionable_item = _first_actionable_guidance_item(guidance_items)
    meta = {
        "source": "none",
        "current_fail_keys": list(fail_keys),
        "current_governing_util": gov_util,
        "target_band_lo": target_lo,
        "target_band_hi": target_hi,
        "has_actionable_item": bool(actionable_item),
        "state_fp": _candidate_cache_key(dict(guidance_disp_state or {})),
    }
    if actionable_item and bool((actionable_item or {}).get("allow_in_target_primary_action")):
        meta["source"] = "blocked_by_in_target_primary_refinement"
        meta["actionable_title"] = (actionable_item or {}).get("title_main") or (actionable_item or {}).get("title")
        if isinstance(guidance_debug, dict):
            guidance_debug["_derived_terminal_state_meta"] = dict(meta)
        return None
    if existing in {"optimal", "very_low_demand"} and terminal_proven:
        meta["source"] = "explicit_render_artifact"
        if isinstance(guidance_debug, dict):
            guidance_debug["_derived_terminal_state_meta"] = dict(meta)
        return existing
    if not fail_keys:
        in_target_band_now = (
            gov_util is not None
            and gov_util >= float(target_lo)
            and gov_util <= float(target_hi)
        )
        if in_target_band_now and not actionable_item:
            meta["source"] = "derived_current_overview"
            if isinstance(guidance_debug, dict):
                guidance_debug["_derived_terminal_state_meta"] = dict(meta)
            return "optimal"
        if gov_util is not None and gov_util < 0.20 and not actionable_item and terminal_proven:
            meta["source"] = "derived_current_overview"
            if isinstance(guidance_debug, dict):
                guidance_debug["_derived_terminal_state_meta"] = dict(meta)
            return "very_low_demand"
        if not actionable_item and terminal_proven:
            meta["source"] = "derived_current_overview"
            if isinstance(guidance_debug, dict):
                guidance_debug["_derived_terminal_state_meta"] = dict(meta)
            return "optimal"
    if isinstance(guidance_debug, dict):
        guidance_debug["_derived_terminal_state_meta"] = dict(meta)
    return None


__all__ = [
    "bind_terminal_state_dependencies",
    "_derive_design_guide_terminal_state_from_current_overview",
    "_design_guide_terminal_state_from_render_artifacts",
]
