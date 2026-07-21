"""Shear evaluation coordination for Inputs app-bridge candidates."""

from __future__ import annotations

from typing import Any


_SHEAR_EVALUATION_DEPENDENCIES: tuple[str, ...] = (
    "_design_width_value_for_app_bridge",
    "_effective_bottom_design_state_for_app_bridge",
    "_float_from_state",
    "_uls_action_from_state_for_app_bridge",
)


def bind_shear_evaluation_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _SHEAR_EVALUATION_DEPENDENCIES
            if name in namespace
        }
    )


def _evaluate_shear_with_state_for_app_bridge(
    state: dict,
    *,
    bottom_updates: dict | None = None,
    shear_updates: dict | None = None,
) -> dict | None:
    from shear_core import ShearInputs, run_shear_calc

    bottom_state = _effective_bottom_design_state_for_app_bridge(state, bottom_updates)
    b = _design_width_value_for_app_bridge(state)
    D = _float_from_state(state, "D", 600.0)
    fc = _float_from_state(state, "fc", 40.0)
    fsy = _float_from_state(state, "fsy", 500.0)
    Ec = _float_from_state(state, "Ec", 30000.0)
    Es = _float_from_state(state, "Es", 200000.0)
    phi = _float_from_state(state, "phi_shear", 0.75)
    d_g = _float_from_state(state, "d_g", 20.0)

    lig_d = _float_from_state(
        shear_updates or state,
        "lig_d",
        _float_from_state(state, "lig_d", 10.0),
    )
    lig_legs = _float_from_state(
        shear_updates or state,
        "lig_legs",
        _float_from_state(state, "lig_legs", 2.0),
    )
    s_lig = _float_from_state(
        shear_updates or state,
        "s_lig",
        _float_from_state(state, "s_lig", 200.0),
    )

    kv_method = str(state.get("k_v_method", "General Îµx-based (Cl. 8.2.4.2)") or "General Îµx-based (Cl. 8.2.4.2)")
    use_general_kv = ("8.2.4.2" in kv_method) or ("Îµ" in kv_method) or ("ex" in kv_method.lower())

    kd_option_selected = str(state.get("k_d_option", "None (no ducts in web)") or "None (no ducts in web)")
    kd_value_map = {
        "None (no ducts in web)": 0.0,
        "0.5 â€“ steel ducts, grouted": 0.5,
        "0.8 â€“ plastic ducts, grouted": 0.8,
        "1.2 â€“ ungrouted ducts": 1.2,
        "Prestressing ducts present (apply k_d)": 0.5,
    }
    k_d = float(kd_value_map.get(kd_option_selected, 0.0))
    sum_duct = _float_from_state(state, "n_ducts", 0.0) * _float_from_state(state, "duct_dia", 0.0)

    inp = ShearInputs(
        b=b,
        D=D,
        d=bottom_state["d_centroid"],
        fc=fc,
        fsy=fsy,
        Ec=Ec,
        Es=Es,
        M_star=_uls_action_from_state_for_app_bridge(state, "M"),
        V_star=_uls_action_from_state_for_app_bridge(state, "V"),
        T_star=_uls_action_from_state_for_app_bridge(state, "T"),
        N_star=_uls_action_from_state_for_app_bridge(state, "N"),
        P_v=_uls_action_from_state_for_app_bridge(state, "P"),
        phi=phi,
        sigma_cp=0.0,
        A_st=bottom_state["Ast_bot"],
        A_pt=0.0,
        f_po=0.0,
        A_ct=_float_from_state(state, "A_ct_default", b * D / 2.0),
        d_g=d_g,
        lig_d=lig_d,
        legs=lig_legs,
        s_lig=s_lig,
        use_general_kv=use_general_kv,
        sum_duct=sum_duct,
        k_d=k_d,
    )
    res = run_shear_calc(inp)
    util = (res.V_eq / res.phi_Vu) if res.phi_Vu > 0 else float("inf")
    phi_vu_max = phi * res.Vu_max_kN
    web_util = (res.V_eq / phi_vu_max) if phi_vu_max > 0 else float("inf")
    return {
        "results": res,
        "util": util,
        "web_util": web_util,
        "lig_d": lig_d,
        "lig_legs": int(lig_legs),
        "s_lig": s_lig,
    }
