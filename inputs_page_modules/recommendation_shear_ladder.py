"""Shear recommendation ladder-state generation."""

from __future__ import annotations

from typing import Any


_SHEAR_RECOMMENDATION_LADDER_DEPENDENCIES: tuple[str, ...] = (
    "GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM",
    "REO_BAR_DIAS",
    "REO_SPACINGS",
    "_activation_shear_state",
    "_candidate_leg_counts",
    "_float_from_state",
    "_geometry_lock_enabled",
    "_int_from_state",
    "_make_auto_design_candidate_key",
    "_resolve_geometry_width_context",
    "_shear_reinforcement_is_active",
    "_shear_state_eligible_for_no_links",
)


def bind_shear_recommendation_ladder_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _SHEAR_RECOMMENDATION_LADDER_DEPENDENCIES
            if name in namespace
        }
    )


def _iter_shear_recommendation_ladder_states(state: dict, *, conservative: bool) -> list[tuple[str, dict]]:
    trials: list[tuple[str, dict]] = []
    geo_lock = _geometry_lock_enabled(state)
    cur_s = float(_float_from_state(state, "s_lig", 0.0) or 0.0)
    cur_legs = max(_int_from_state(state, "lig_legs", 2), 2)
    cur_dia = max(_int_from_state(state, "lig_d", 10), 10)
    width_key, _, cur_w = _resolve_geometry_width_context(state)
    cur_d = float(_float_from_state(state, "D", 600.0) or 600.0)
    cur_fc = float(_float_from_state(state, "fc", 32.0) or 32.0)

    def _push(branch: str, st: dict) -> None:
        trials.append((branch, dict(st)))

    if conservative:
        if _shear_reinforcement_is_active(state):
            looser = [float(x) for x in REO_SPACINGS if float(x) > cur_s + 1e-9]
            for s in sorted(looser)[:4]:
                ns = dict(state)
                ns["lig_legs"] = int(max(_int_from_state(state, "lig_legs", 2), 2))
                ns["lig_d"] = int(max(_int_from_state(state, "lig_d", 10), 10))
                ns["s_lig"] = float(s)
                _push("spacing_looser", ns)
            for nl in _candidate_leg_counts(cur_legs, conservative=True):
                ns = dict(state)
                ns["lig_legs"] = int(max(2, nl))
                ns["lig_d"] = int(cur_dia)
                ns["s_lig"] = float(cur_s)
                _push("legs_down", ns)
            smaller_dias = [int(d) for d in REO_BAR_DIAS if int(d) < int(cur_dia) and int(d) >= 10]
            for nd in sorted(smaller_dias, reverse=True)[:3]:
                ns = dict(state)
                ns["lig_d"] = int(nd)
                ns["lig_legs"] = int(cur_legs)
                ns["s_lig"] = float(cur_s)
                _push("dia_down", ns)
        if _int_from_state(state, "lig_legs", 0) > 0 and _shear_state_eligible_for_no_links(state):
            ns = dict(state)
            ns["lig_legs"] = 0
            ns["lig_d"] = 0
            ns["s_lig"] = float(max(_float_from_state(state, "s_lig", 200.0), 1.0))
            _push("no_ligs", ns)
        return trials

    if not _shear_reinforcement_is_active(state):
        act = _activation_shear_state(state)
        if _make_auto_design_candidate_key(act) != _make_auto_design_candidate_key(state):
            _push("shear_activation", act)
        return trials

    eligible_s = [float(x) for x in REO_SPACINGS if float(x) < cur_s - 1e-9]
    for s in sorted(eligible_s)[:5]:
        ns = dict(state)
        ns["lig_legs"] = int(cur_legs)
        ns["lig_d"] = int(cur_dia)
        ns["s_lig"] = float(s)
        _push("spacing_tighter", ns)
    for nl in _candidate_leg_counts(cur_legs, conservative=False):
        if nl < 2 or nl == cur_legs:
            continue
        ns = dict(state)
        ns["lig_legs"] = int(nl)
        ns["lig_d"] = int(cur_dia)
        ns["s_lig"] = float(cur_s)
        _push("legs_up", ns)
    for nd in REO_BAR_DIAS:
        if int(nd) > int(cur_dia) and int(nd) <= 24:
            ns = dict(state)
            ns["lig_d"] = int(nd)
            ns["lig_legs"] = int(cur_legs)
            ns["s_lig"] = float(cur_s)
            _push("dia_up", ns)

    if not geo_lock:
        for delta in GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM:
            ns = dict(state)
            ns["D"] = float(int(round(max(350.0, cur_d + float(delta)) / 10.0) * 10))
            _push("depth_up", ns)
        for delta in GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM:
            ns = dict(state)
            nw = float(int(round(max(250.0, cur_w + float(delta)) / 10.0) * 10))
            ns[width_key] = nw
            if width_key != "b":
                ns["b"] = nw
            _push("width_up", ns)

    if cur_fc < 65.0:
        ns = dict(state)
        ns["fc"] = float(min(65.0, int(round((cur_fc + 5.0) / 5.0) * 5)))
        if abs(float(ns["fc"]) - cur_fc) > 1e-9:
            _push("material_fc", ns)

    return trials
