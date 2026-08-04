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
from shear_calculation_runtime import ShearInputs, run_shear_calc
from state_runtime_gateway import resolve_design_actions


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

    Does **not** change structural formulas — it merges envelope utilisation, sectional
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
    # Preserve 0 legs / 0 spacing — ``0 or 2.0`` incorrectly upgraded "no shear ligs" to 2 legs.
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
                st_state.get("inputs_k_v_method", "General εₓ-based (Cl. 8.2.4.2)"),
            ),
        ),
    )
    use_general_kv = "ε" in str(kv_method) or "8.2.4.2" in str(kv_method)

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
        "0.5 – steel ducts, grouted": 0.5,
        "0.8 – plastic ducts, grouted": 0.8,
        "1.2 – ungrouted ducts": 1.2,
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
    """Single run of shear_core from session: live_state, actions, results, phi, k_d, use_general_kv."""
    ctx = _shear_calc_context(st_state)
    res = run_shear_calc(ctx["inputs"])
    # When auto spacing is off, keep live run_shear_calc outputs so manual link spacing
    # (shear_s_lig → s_lig) drives φV_u in the UI. When on, prefer canonical φV_u from
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
    """
    Pure helper for Inputs + Shear page.
    Calls run_shear_calc() directly (no writes).
    """
    bundle = build_shear_calc_bundle_from_state(st_state)
    ctx = _shear_calc_context(st_state)
    inp = ctx["inputs"]
    actions = bundle["actions_used"]
    V_star = float(actions["Vu"])

    if abs(V_star - 0.0) < 1e-6:
        print("[DEBUG] Vu being treated as zero in shear table")

    res = bundle["results"]
    phi = float(bundle["phi"])

    def _status_from_util(u: float | None):
        if u is None:
            return "—"
        if u <= 1.0:
            return "NEAR LIMIT" if u >= 0.9 else "PASS"
        return "FAIL"

    util = (res.V_eq / res.phi_Vu) if res.phi_Vu > 0 else float("nan")
    util_sectional = util if util == util else None
    ok = (util <= 1.0) if util == util else None
    status = _status_from_util(util) if ok is not None else "—"

    lig_d = float(st_state.get("lig_d", getattr(inp, "lig_d", 0.0)) or 0.0)
    legs = float(st_state.get("lig_legs", getattr(inp, "legs", 0.0)) or 0.0)
    s_prov = float(st_state.get("s_lig", getattr(inp, "s_lig", 0.0)) or 0.0)
    s_sec = st_state.get("shear_sectional_check_spacing_mm")
    s_sec_f = float(s_sec) if s_sec is not None else s_prov
    s_req_raw = st_state.get("shear_required_spacing_mm")
    s_req = float(s_req_raw) if s_req_raw is not None else None
    s_eff_raw = st_state.get("shear_effective_spacing_mm")
    s_eff_f = float(s_eff_raw) if s_eff_raw is not None else s_sec_f
    D_mm = float(st_state.get("D", 600.0) or 600.0)
    s_max_code_mm = min(0.75 * max(D_mm, 0.0), 500.0)
    links_present = bool(lig_d > 0.0 or legs > 0)
    link_detail_failures: list[str] = []
    if links_present:
        if lig_d <= 0.0:
            link_detail_failures.append("link diameter must be positive when shear links are present")
        if legs < 2:
            link_detail_failures.append("at least 2 shear-link legs are required when links are present")
        if s_prov <= 0.0:
            link_detail_failures.append("link spacing must be positive when shear links are present")
        elif s_prov > s_max_code_mm + 1e-9:
            link_detail_failures.append(
                f"provided link spacing {s_prov:.0f} mm exceeds code maximum {s_max_code_mm:.0f} mm"
            )
        if s_req is not None and s_prov > float(s_req) + 0.51:
            link_detail_failures.append(
                f"provided link spacing {s_prov:.0f} mm exceeds required spacing {float(s_req):.0f} mm"
            )
    link_detail_status = "FAIL" if link_detail_failures else ("PASS" if links_present else "INFO")
    link_detail_reason = "; ".join(link_detail_failures) if link_detail_failures else (
        "provided shear-link detailing is within spacing/leg limits"
        if links_present else
        "no shear links provided"
    )
    phi_Vu_max = phi * res.Vu_max_kN
    util_web = (res.V_eq / phi_Vu_max) if phi_Vu_max > 0 else float("nan")
    util_web_value = util_web if util_web == util_web else None
    ok_web = (util_web <= 1.0) if util_web == util_web else None
    status_web = _status_from_util(util_web) if ok_web is not None else "—"

    c_truth = compute_canonical_shear_truth(
        st_state,
        bundle=bundle,
        provided_spacing_mm=s_prov,
        required_spacing_mm=s_req,
        effective_spacing_mm=s_eff_f,
    )
    u_gov = c_truth.get("shear_util_governing")
    truth_status = str(c_truth.get("shear_truth_status") or "—")
    util_display = u_gov if u_gov is not None and u_gov == u_gov else util
    status_display = truth_status if truth_status not in ("", "—") else status
    _bundle_complete = session_final_shear_truth_bundle_complete(st_state)
    summary_shear_truth_consume_reason = (
        "explicit_final_truth_bundle" if _bundle_complete else "recomputed_local_bundle_missing_final_truth"
    )
    if not _bundle_complete:
        ds_u = str(st_state.get("shear_design_status") or "").strip().upper()
        if ds_u == "INVALID":
            status_display = "INVALID"
            util_display = None
        else:
            # When explicit normalized final truth is missing, fall back to the live local
            # sectional shear check rather than forcing a red summary state.
            status_display = truth_status if truth_status not in ("", "—") else status
            util_display = u_gov if u_gov is not None and u_gov == u_gov else util_sectional
    torsion_text = "NOT REQUIRED" if not res.torsion_required else "REQUIRED"
    shear_design_status = str(st_state.get("shear_design_status") or "").strip().upper()

    sectional_shear_capacity_row = sync_legacy_value_limit({
        "uid": "shear_check8",
        "title": "Sectional shear capacity",
        "capacity": f"φVu = {res.phi_Vu:.1f} kN",
        "action": f"V*eq = {res.V_eq:.1f} kN",
        "util": _fmt_row_util(util_sectional),
        "status": "INVALID" if shear_design_status == "INVALID" and util_sectional is None else status,
        "route_page": "shear",
    })
    torsion_cracking_row = sync_legacy_value_limit({
        "uid": "shear_check1",
        "title": "Torsion cracking check",
        "capacity": f"Reference: 0.25 φ T_cr = {res.torsion_required_limit:.1f} kNm",
        "action": f"Torsion design {torsion_text}",
        "util": "—",
        "status": "INFO",
        "is_informational": True,
        "route_page": "shear",
    })
    web_crushing_row = sync_legacy_value_limit({
        "uid": "shear_check9",
        "title": "Web-crushing strength",
        "capacity": f"φVu,max = {phi_Vu_max:.1f} kN",
        "action": f"V*eq = {res.V_eq:.1f} kN",
        "util": _fmt_row_util(util_web_value),
        "status": status_web,
        "route_page": "shear",
    })
    link_detailing_row = sync_legacy_value_limit({
        "uid": "shear_link_detailing",
        "title": "Shear link detailing",
        "capacity": (
            f"s_max = {s_max_code_mm:.0f} mm"
            if s_req is None
            else f"s_req = {float(s_req):.0f} mm; s_max = {s_max_code_mm:.0f} mm"
        ),
        "action": f"{int(round(legs))}-leg N{int(round(lig_d))} @ {s_prov:.0f} mm" if links_present else "No shear links",
        "util": "—",
        "status": link_detail_status,
        "reason": link_detail_reason,
        "is_informational": not links_present,
        "route_page": "shear",
    })

    summary_rows = [sectional_shear_capacity_row]
    summary_rows.extend([
        torsion_cracking_row,
        web_crushing_row,
        link_detailing_row,
    ])

    mcft_detail_rows = [
        sync_legacy_value_limit({
            "uid": "shear_check2",
            "title": "Equivalent design shear",
            "capacity": "—",
            "action": f"V*eq = {res.V_eq:.1f} kN",
            "util": "—",
            "status": "—",
            "route_page": "shear",
        }),
        sync_legacy_value_limit({
            "uid": "shear_check4",
            "title": "Longitudinal strain",
            "capacity": "—",
            "action": f"εx = {res.eps_x:.5f}",
            "util": "—",
            "status": "—",
            "route_page": "shear",
        }),
        sync_legacy_value_limit({
            "uid": "shear_check5",
            "title": "Shear model parameters",
            "capacity": "—",
            "action": f"k_v = {res.k_v:.3f}, θ_v = {res.theta_v_deg:.1f}°",
            "util": "—",
            "status": "—",
            "route_page": "shear",
        }),
        sync_legacy_value_limit({
            "uid": "shear_check6",
            "title": "Concrete shear strength",
            "capacity": "—",
            "action": f"Vuc = {res.Vuc_kN:.1f} kN",
            "util": "—",
            "status": "—",
            "route_page": "shear",
        }),
        sync_legacy_value_limit({
            "uid": "shear_check7",
            "title": "Steel shear strength",
            "capacity": "—",
            "action": f"Vs = Vus = {res.Vus_kN:.1f} kN",
            "util": "—",
            "status": "—",
            "route_page": "shear",
        }),
    ]


    rows = list(summary_rows) + list(mcft_detail_rows)

    def _status_priority(value: str) -> int:
        status_norm = str(value or "").strip().upper()
        if status_norm == "INVALID":
            return 0
        if status_norm == "FAIL":
            return 1
        if status_norm == "NEAR LIMIT":
            return 2
        if status_norm == "PASS":
            return 3
        if status_norm in {"—", "", "INFO"}:
            return 9
        return 8

    def _candidate(
        *,
        name: str,
        source: str,
        demand_value: float | None,
        capacity_value: float | None,
        util_value: float | None,
        status_value: str,
        reason_value: str,
        demand_display: str,
        capacity_display: str,
    ) -> dict:
        return {
            "name": name,
            "source": source,
            "demand_value": demand_value,
            "capacity_value": capacity_value,
            "util": util_value,
            "status": str(status_value or "—"),
            "reason": str(reason_value or ""),
            "demand_display": demand_display,
            "capacity_display": capacity_display,
        }

    explicit_governing_util = st_state.get("shear_governing_util")
    if explicit_governing_util is None:
        explicit_governing_util = c_truth.get("shear_governing_util")
    explicit_governing_status = str(
        st_state.get("shear_governing_status") or c_truth.get("shear_governing_status") or ""
    ).strip()
    explicit_governing_reason = str(
        st_state.get("shear_governing_reason") or c_truth.get("shear_governing_reason") or ""
    ).strip()
    explicit_governing_source = str(
        st_state.get("shear_governing_source") or c_truth.get("shear_governing_source") or ""
    ).strip()
    explicit_governing_name = str(
        st_state.get("shear_governing_check_name") or c_truth.get("shear_governing_check_name") or ""
    ).strip()
    explicit_governing_demand = st_state.get("shear_governing_demand_kN")
    if explicit_governing_demand is None:
        explicit_governing_demand = c_truth.get("shear_governing_demand_kN")
    explicit_governing_capacity = st_state.get("shear_governing_capacity_kN")
    if explicit_governing_capacity is None:
        explicit_governing_capacity = c_truth.get("shear_governing_capacity_kN")

    explicit_canonical_truth_present = bool(
        explicit_governing_status
        or explicit_governing_util is not None
        or explicit_governing_reason
        or explicit_governing_source
    )

    governing_candidate = None
    if explicit_canonical_truth_present:
        governing_candidate = _candidate(
            name=explicit_governing_name or "Final published shear truth",
            source=explicit_governing_source or "canonical_published_shear_truth",
            demand_value=explicit_governing_demand,
            capacity_value=explicit_governing_capacity,
            util_value=explicit_governing_util,
            status_value=explicit_governing_status or status_display,
            reason_value=explicit_governing_reason or str(c_truth.get("shear_truth_reason") or ""),
            demand_display=(
                f"V*eq = {float(explicit_governing_demand):.1f} kN"
                if explicit_governing_demand is not None
                else (f"V*eq = {res.V_eq:.1f} kN" if _bundle_complete else "V*eq = —")
            ),
            capacity_display=(
                f"φVgov = {float(explicit_governing_capacity):.1f} kN"
                if explicit_governing_capacity is not None
                else (f"φVu = {res.phi_Vu:.1f} kN" if _bundle_complete else "φVu = —")
            ),
        )
        governing_candidate["selection_origin"] = "explicit_canonical_published_truth"
    else:
        candidates = [
            _candidate(
                name="Sectional shear capacity",
                source="sectional_shear_capacity",
                demand_value=float(res.V_eq),
                capacity_value=float(res.phi_Vu),
                util_value=util_sectional,
                status_value=sectional_shear_capacity_row.get("status"),
                reason_value="sectional_shear_capacity_check",
                demand_display=f"V*eq = {res.V_eq:.1f} kN",
                capacity_display=f"φVu = {res.phi_Vu:.1f} kN",
            ),
            _candidate(
                name="Link spacing / effective spacing",
                source="spacing_effective_spacing_check",
                demand_value=spacing_demand_mm,
                capacity_value=spacing_capacity_mm,
                util_value=util_spacing,
                status_value=spacing_truth_row.get("status"),
                reason_value=spacing_reason or "link_spacing_effective_spacing_check",
                demand_display=f"Spacing demand = {spacing_demand_mm:.0f} mm" if spacing_demand_mm is not None else "Spacing demand = —",
                capacity_display=f"Spacing capacity = {spacing_capacity_mm:.0f} mm" if spacing_capacity_mm is not None else "Spacing capacity = —",
            ),
            _candidate(
                name="Web-crushing strength",
                source="web_crushing_strength",
                demand_value=float(res.V_eq),
                capacity_value=float(phi_Vu_max),
                util_value=util_web_value,
                status_value=web_crushing_row.get("status"),
                reason_value="web_crushing_strength_check",
                demand_display=f"V*eq = {res.V_eq:.1f} kN",
                capacity_display=f"φVu,max = {phi_Vu_max:.1f} kN",
            ),
        ]
        governing_candidates = [
            candidate
            for candidate in candidates
            if str(candidate.get("status") or "").strip().upper() not in {"INFO", "—", ""}
            and (
                candidate.get("util") is not None
                or str(candidate.get("status") or "").strip().upper() == "INVALID"
            )
        ]
        if governing_candidates:
            governing_candidate = sorted(
                governing_candidates,
                key=lambda candidate: (
                    _status_priority(candidate.get("status")),
                    -(float(candidate.get("util")) if candidate.get("util") is not None else -1.0),
                ),
            )[0]
            governing_candidate["selection_origin"] = "recomputed_local_bundle"

    if governing_candidate is None:
        governing_candidate = _candidate(
            name="Final published shear truth",
            source="final_published_shear_truth_fallback",
            demand_value=float(res.V_eq),
            capacity_value=float(res.phi_Vu),
            util_value=(util_display if util_display == util_display else None) if util_display is not None else None,
            status_value=status_display,
            reason_value=str(c_truth.get("shear_truth_reason") or summary_shear_truth_consume_reason or ""),
            demand_display=f"V*eq = {res.V_eq:.1f} kN",
            capacity_display=f"φVu = {res.phi_Vu:.1f} kN",
        )
        governing_candidate["selection_origin"] = "final_truth_fallback"

    summary_governing_util = governing_candidate.get("util")
    summary_governing_status = str(governing_candidate.get("status") or "").strip() or status_display
    summary_governing_reason = str(governing_candidate.get("reason") or "").strip()
    summary_governing_source = str(governing_candidate.get("source") or "").strip()
    if link_detail_failures:
        governing_candidate = {
            **dict(governing_candidate or {}),
            "name": "Shear link detailing",
            "source": "shear_link_detailing",
            "demand_value": s_prov,
            "capacity_value": s_req if s_req is not None else s_max_code_mm,
            "util": None,
            "status": "FAIL",
            "reason": link_detail_reason,
            "demand_display": f"Provided spacing = {s_prov:.0f} mm",
            "capacity_display": (
                f"Required spacing = {float(s_req):.0f} mm"
                if s_req is not None
                else f"Code maximum spacing = {s_max_code_mm:.0f} mm"
            ),
            "selection_origin": "provided_link_detailing_check",
        }
        summary_governing_util = None
        summary_governing_status = "FAIL"
        summary_governing_reason = link_detail_reason
        summary_governing_source = "shear_link_detailing"
    summary_display_capacity = f"φVu = {res.phi_Vu:.1f} kN" if _bundle_complete else "φVu = —"
    summary_display_demand = f"V*eq = {res.V_eq:.1f} kN" if _bundle_complete else "V*eq = —"


    return {
        "summary_phiVu_kN": res.phi_Vu,
        "summary_Veq_kN": res.V_eq,
        "summary_Vstar_kN": float(V_star),
        "summary_util": summary_governing_util,
        "summary_status": summary_governing_status,
        "summary_capacity": governing_candidate.get("capacity_display"),
        "summary_demand": governing_candidate.get("demand_display"),
        "summary_reason": summary_governing_reason,
        "summary_governing_check_name": governing_candidate.get("name"),
        "summary_governing_demand_kN": governing_candidate.get("demand_value"),
        "summary_governing_capacity_kN": governing_candidate.get("capacity_value"),
        "summary_governing_util": summary_governing_util,
        "summary_governing_status": summary_governing_status,
        "summary_governing_reason": summary_governing_reason,
        "summary_governing_source": summary_governing_source,
        "summary_display_capacity": summary_display_capacity,
        "summary_display_demand": summary_display_demand,
        "summary_display_capacity_label": "Calculated capacity",
        "summary_display_demand_label": "Applied design action",
        "summary_display_source": "sectional_required_shear",
        "summary_governing_selection_origin": str(governing_candidate.get("selection_origin") or ""),
        "summary_governing_explicit_canonical_truth_present": bool(explicit_canonical_truth_present),
        "rows": rows,
        "summary_rows": summary_rows,
        "mcft_detail_rows": mcft_detail_rows,
        "actions_used": actions,
        "shear_provided_spacing_mm": c_truth.get("shear_provided_spacing_mm"),
        "shear_effective_spacing_mm": c_truth.get("shear_effective_spacing_mm"),
        "shear_required_spacing_mm": c_truth.get("shear_required_spacing_mm"),
        "shear_truth_status": c_truth.get("shear_truth_status") if _bundle_complete else status_display,
        "shear_truth_reason": c_truth.get("shear_truth_reason"),
        "shear_truth_inconsistent_status_override": c_truth.get("shear_truth_inconsistent_status_override"),
        "final_shear_truth_bundle_complete": bool(_bundle_complete),
        "summary_shear_truth_consume_reason": summary_shear_truth_consume_reason,
    }
