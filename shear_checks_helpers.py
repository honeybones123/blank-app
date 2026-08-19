from copy import copy
from dataclasses import astuple
from functools import lru_cache
from typing import Any, Dict, Tuple

import math

from calculations.shear import (
    compute_canonical_shear_truth_from_bundle,
    format_shear_row_util as _fmt_row_util,
    resolve_shear_spacing_truth,
    session_final_shear_truth_bundle_complete,
    shear_truth_status_from_util as _truth_status_from_util,
)
from engineering_check_ui import sync_legacy_value_limit
from shear_calculation_runtime import ShearInputs, ShearResults, run_shear_calc
from state_runtime_gateway import resolve_design_actions
from inputs_application.authoritative_check_packs import (
    authoritative_check_pack_or_unavailable,
)


@lru_cache(maxsize=128)
def _run_shear_calc_for_inputs(input_values: tuple[Any, ...]) -> ShearResults:
    """Reuse the existing pure shear calculation for identical typed inputs."""

    return run_shear_calc(ShearInputs(*input_values))


def _normalise_canonical_shear_truth_bundle(
    bundle_or_state: Dict[str, Any] | None,
    *,
    st_state: Dict[str, Any],
) -> Tuple[Dict[str, Any], str]:
    """
    Ensure a shear calc bundle has an ``inputs`` key (ShearInputs) without stripping
    richer bundle fields. Accepts either a full bundle, the partial dict returned by
    ``build_shear_calc_bundle_from_state`` (which omits ``inputs``), or a plain
    session/overview state dict.
    """
    def _ensure_inputs(nb: Dict[str, Any]) -> Dict[str, Any]:
        if nb.get("inputs") is not None:
            return nb
        ctx_src = nb.get("live_state") if isinstance(nb.get("live_state"), dict) else st_state
        out = dict(nb)
        out["inputs"] = _shear_calc_context(ctx_src)["inputs"]
        return out

    if bundle_or_state is None or not isinstance(bundle_or_state, dict):
        nb = _ensure_inputs(build_shear_calc_bundle_from_state(st_state))
        return nb, "empty"

    b = dict(bundle_or_state)
    has_inputs = b.get("inputs") is not None
    has_results = b.get("results") is not None

    if has_inputs and has_results:
        return b, "bundle"
    if has_results and not has_inputs:
        return _ensure_inputs(b), "bundle"

    nb = _ensure_inputs(build_shear_calc_bundle_from_state(bundle_or_state))
    for k, v in b.items():
        if k not in nb:
            nb[k] = v
    return nb, "plain_state"


def compute_canonical_shear_truth(
    st_state: Dict[str, Any],
    *,
    zone_payload: Dict[str, Any] | None = None,
    provided_spacing_mm: float | None = None,
    required_spacing_mm: float | None = None,
    effective_spacing_mm: float | None = None,
    bundle: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Single publication contract for shear pass/fail vs utilisation and spacing truth.

    Does **not** change structural formulas â€” it merges envelope utilisation, sectional
    utilisation, web utilisation, and provided vs effective vs required spacing so the UI
    and solvers cannot show PASS while governing envelope utilisation is > 1.0 or while
    provided detailing is materially looser than the governing required spacing.
    """
    nb, canonical_shear_truth_input_shape = _normalise_canonical_shear_truth_bundle(
        bundle, st_state=st_state
    )
    return compute_canonical_shear_truth_from_bundle(
        st_state,
        bundle=nb,
        canonical_shear_truth_input_shape=canonical_shear_truth_input_shape,
        zone_payload=zone_payload,
        provided_spacing_mm=provided_spacing_mm,
        required_spacing_mm=required_spacing_mm,
        effective_spacing_mm=effective_spacing_mm,
    )


def _shear_calc_context(st_state: Dict[str, Any]) -> Dict[str, Any]:
    """Shared extraction: live dict, actions, and ShearInputs (no I/O)."""
    b = float(st_state.get("b") or 300.0)
    D = float(st_state.get("D") or 600.0)
    d = float(st_state.get("d") or 0.0)
    fc = float(st_state.get("fc") or 32.0)
    fsy = float(st_state.get("fsy") or 500.0)
    Ec = float(st_state.get("Ec") or 30000.0)
    Es = float(st_state.get("Es") or 200000.0)

    actions = resolve_design_actions(st_state)
    M_star = float(actions["Mu"])
    V_star = float(actions["Vu"])
    T_star = float(actions["Tu"])
    N_star = float(actions["Nu"])
    P_v = float(actions["Pu"])

    lig_d = float(st_state.get("lig_d") or 10.0)
    # Preserve 0 legs / 0 spacing â€” ``0 or 2.0`` incorrectly upgraded "no shear ligs" to 2 legs.
    try:
        legs = float(st_state.get("lig_legs", 0.0))
    except (TypeError, ValueError):
        legs = 0.0
    try:
        s_lig = float(st_state.get("s_lig", 200.0))
    except (TypeError, ValueError):
        s_lig = 200.0

    phi = float(st_state.get("phi_shear") or 0.75)

    kv_method = st_state.get(
        "k_v_method",
        st_state.get(
            "kv_method",
            st_state.get(
                "shear_k_v_method",
                st_state.get("inputs_k_v_method", "General Îµâ‚“-based (Cl. 8.2.4.2)"),
            ),
        ),
    )
    use_general_kv = "Îµ" in str(kv_method) or "8.2.4.2" in str(kv_method)

    A_st = float(
        st_state.get("shear_A_st")
        or (4 * (math.pi * 20**2 / 4))
    )
    A_pt = float(st_state.get("shear_A_pt") or 0.0)
    f_po = float(st_state.get("shear_f_po") or 0.0)
    A_ct_default = float(st_state.get("A_ct_default") or ((b * D / 2.0) if b and D else 0.0))
    A_ct = float(st_state.get("shear_A_ct") or A_ct_default)
    d_g = float(st_state.get("shear_d_g") or st_state.get("d_g") or 20.0)
    sum_duct = float(st_state.get("shear_sum_duct") or st_state.get("sum_duct") or 0.0)
    kd_option_selected = str(
        st_state.get("shear_k_d_option")
        or st_state.get("k_d_option")
        or "None (no ducts in web)"
    )
    kd_value_map = {
        "None (no ducts in web)": 0.0,
        "0.5 â€“ steel ducts, grouted": 0.5,
        "0.8 â€“ plastic ducts, grouted": 0.8,
        "1.2 â€“ ungrouted ducts": 1.2,
    }
    k_d = float(kd_value_map.get(kd_option_selected, 0.0))

    db_bot_1 = float(st_state.get("db_bot_1") or st_state.get("db_bot") or 20.0)
    db_bot_2 = float(st_state.get("db_bot_2") or db_bot_1)

    sigma_cp = float(st_state.get("sigma_cp") or 0.0)

    live_state: Dict[str, Any] = {
        "b": b,
        "D": D,
        "d": d,
        "fc": fc,
        "fsy": fsy,
        "Ec": Ec,
        "Es": Es,
        "Mu": M_star,
        "Vu": V_star,
        "Tu": T_star,
        "Nu": N_star,
        "Pu": P_v,
        "lig_d": lig_d,
        "lig_legs": legs,
        "s_lig": s_lig,
        "A_st": A_st,
        "A_pt": A_pt,
        "f_po": f_po,
        "A_ct": A_ct,
        "d_g": d_g,
        "sigma_cp": sigma_cp,
        "sum_duct": sum_duct,
        "db_bot_1": db_bot_1,
        "db_bot_2": db_bot_2,
    }

    inp = ShearInputs(
        b=b, D=D, d=d, fc=fc, fsy=fsy, Ec=Ec, Es=Es,
        M_star=float(M_star or 0.0),
        V_star=float(V_star or 0.0),
        T_star=float(T_star or 0.0),
        N_star=float(N_star or 0.0),
        P_v=float(P_v or 0.0),
        phi=phi,
        sigma_cp=sigma_cp,
        A_st=A_st,
        A_pt=A_pt,
        f_po=f_po,
        A_ct=A_ct,
        d_g=d_g,
        lig_d=lig_d, legs=legs, s_lig=s_lig,
        use_general_kv=use_general_kv,
        sum_duct=sum_duct,
        k_d=k_d,
    )

    return {
        "live_state": live_state,
        "actions_used": actions,
        "phi": phi,
        "k_d": k_d,
        "use_general_kv": use_general_kv,
        "inputs": inp,
    }


def build_live_canonical_shear_state(st_state: Dict[str, Any]) -> Dict[str, Any]:
    """Snapshot of shear-related session fields (geometry, actions, links, bars) for UI / debug."""
    return dict(_shear_calc_context(st_state)["live_state"])


def build_shear_calc_bundle_from_state(st_state: Dict[str, Any]) -> Dict[str, Any]:
    """Single shear-core result for the current typed inputs, reused when inputs are identical."""
    ctx = _shear_calc_context(st_state)
    # ``run_shear_calc`` is explicitly a pure typed calculation. Cache only by
    # every ShearInputs field, then copy the result before applying the existing
    # session-dependent canonical overlay below. This removes repeated work in
    # one render without introducing a second engineering implementation.
    input_values = tuple(astuple(ctx["inputs"]))
    res = copy(_run_shear_calc_for_inputs(input_values))
    # When auto spacing is off, keep live run_shear_calc outputs so manual link spacing
    # (shear_s_lig â†’ s_lig) drives Ï†V_u in the UI. When on, prefer canonical Ï†V_u from
    # _compute_shear_capacity (sectional check uses governing envelope spacing in-memory;
    # shared s_lig stays the user-provided input).
    use_canonical = bool(st_state.get("shear_auto_design", False))
    canonical_phi_vu = st_state.get("phi_Vu_cap")
    if use_canonical and canonical_phi_vu not in (None, 0, 0.0):
        res.phi_Vu = float(st_state.get("phi_Vu_cap") or res.phi_Vu)
        res.Vuc_kN = float(st_state.get("shear_Vuc_kN") or res.Vuc_kN)
        res.Vus_kN = float(st_state.get("shear_Vus_kN") or res.Vus_kN)
        res.Vu_total_kN = float(st_state.get("shear_Vu_total_kN") or res.Vu_total_kN)
        res.k_v = float(st_state.get("shear_k_v") or res.k_v)
        res.theta_v_deg = float(st_state.get("shear_theta_v_deg") or res.theta_v_deg)
        res.theta_v_rad = float(st_state.get("shear_theta_v_rad") or res.theta_v_rad)
        res.shear_ok = bool(res.phi_Vu >= res.V_eq)
    return {
        "live_state": ctx["live_state"],
        "actions_used": ctx["actions_used"],
        "results": res,
        "phi": ctx["phi"],
        "k_d": ctx["k_d"],
        "use_general_kv": ctx["use_general_kv"],
    }


def build_shear_check_rows_from_state(st_state: Dict[str, Any]) -> Dict[str, Any]:
    """Project the current V2 shear result without a page-local fallback."""

    return authoritative_check_pack_or_unavailable(st_state, "shear")


__all__ = [
    "build_live_canonical_shear_state",
    "build_shear_calc_bundle_from_state",
    "build_shear_check_rows_from_state",
    "compute_canonical_shear_truth",
    "resolve_shear_spacing_truth",
    "session_final_shear_truth_bundle_complete",
]

