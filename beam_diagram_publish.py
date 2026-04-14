# beam_diagram_publish.py
# Headless SLS/ULS beam diagram publish for Crack / global pipeline (no Streamlit widgets).

from __future__ import annotations

import numpy as np
import streamlit as st

from state_and_helpers import get_param, update_results

_LOADING_OPTIONS_SINGLE = [
    "Simple beam – UDL over entire span",
    "Simple beam – partial UDL from left (length a)",
    "Simple beam – multiple point loads",
    "Cantilever – multiple point loads",
    "Cantilever – UDL over entire span",
    "Overhanging beam – right overhang with point load at free end",
]


def _ms_support_clamped(j: int, n_spans: int, raw: str) -> str:
    raw = str(raw or "Pinned").strip()
    if j == 1:
        return raw if raw in ("Pinned", "Fixed") else "Pinned"
    if j == n_spans + 1:
        return raw if raw in ("Pinned", "Roller", "Fixed") else "Pinned"
    return raw if raw in ("Pinned", "Roller") else "Pinned"


def publish_beam_diagram_arrays_from_session_state() -> None:
    """
    Recompute beam x / M_sls (and ULS companions) from current session + shared inputs,
    mirroring Beam Actions & Diagrams, and publish via update_results().

    Skips work when crack_bmd_cache_fingerprint already matches and moment arrays are valid.
    """
    from sfd_bmd_page import (
        _clamp_x,
        _compute_diagram_arrays,
        _defl_support_type_from_selection,
        diagram_cache_fingerprint,
    )

    gamma_g = 1.2
    gamma_q = 1.5

    beam_system_mode = str(get_param("design_beam_system_mode", "Single span") or "Single span").strip()

    params: dict = {}
    case = ""
    L = 0.0
    w_sls = None
    w_uls = None
    P_sls = None
    P_uls = None
    P_sls_total = None
    P_uls_total = None
    point_loads_sls = None
    point_loads_uls = None

    if beam_system_mode == "Multi-span":
        case = "Multi-span continuous beam"
        n_spans = int(round(float(get_param("design_span_count", 2.0) or 2.0)))
        n_spans = max(2, min(5, n_spans))
        node_positions = [0.0]
        for i in range(1, n_spans + 1):
            Li = max(0.2, float(get_param(f"design_span_len_{i}", 4.0) or 4.0))
            node_positions.append(node_positions[-1] + float(Li))
        L = float(node_positions[-1])
        support_types = [
            _ms_support_clamped(j, n_spans, str(get_param(f"design_support_type_{j}", "Pinned") or "Pinned"))
            for j in range(1, n_spans + 2)
        ]
        psi_point = float(get_param("psi_point", 0.4) or 0.4)
        psi_udl = float(get_param("psi_udl", 0.4) or 0.4)

        n_point = int(round(float(get_param("design_ms_point_count", 2.0) or 2.0)))
        n_point = max(0, min(8, n_point))
        ms_rows = []
        for i in range(1, n_point + 1):
            g_i = float(get_param(f"design_ms_G_{i}", 30.0) or 0.0)
            q_i = float(get_param(f"design_ms_Q_{i}", 20.0) or 0.0)
            x_i = _clamp_x(float(get_param(f"design_ms_x_{i}", L * i / max(1, n_point + 1)) or 0.0), float(L))
            ms_rows.append(
                {
                    "x_m": x_i,
                    "P_sls": g_i + psi_point * q_i,
                    "P_uls": gamma_g * g_i + gamma_q * q_i,
                }
            )
        ms_rows.sort(key=lambda r: r["x_m"])
        point_loads_sls = [{"x_m": r["x_m"], "P_kN": r["P_sls"]} for r in ms_rows]
        point_loads_uls = [{"x_m": r["x_m"], "P_kN": r["P_uls"]} for r in ms_rows]
        P_sls_total = float(sum(r["P_sls"] for r in ms_rows))
        P_uls_total = float(sum(r["P_uls"] for r in ms_rows))

        n_udl = int(round(float(get_param("design_ms_udl_count", 1.0) or 1.0)))
        n_udl = max(0, min(8, n_udl))
        ms_udl_rows = []
        for i in range(1, n_udl + 1):
            g_i = float(get_param(f"design_ms_g_{i}", 5.0) or 0.0)
            q_i = float(get_param(f"design_ms_q_{i}", 3.0) or 0.0)
            x0_raw = float(get_param(f"design_ms_x0_{i}", 0.0) or 0.0)
            x1_raw = float(get_param(f"design_ms_x1_{i}", L) or float(L))
            x0 = _clamp_x(min(x0_raw, x1_raw), float(L))
            x1 = _clamp_x(max(x0_raw, x1_raw), float(L))
            if x1 <= x0:
                continue
            ms_udl_rows.append(
                {
                    "x_start_m": x0,
                    "x_end_m": x1,
                    "w_sls": g_i + psi_udl * q_i,
                    "w_uls": gamma_g * g_i + gamma_q * q_i,
                }
            )
        ms_udl_rows.sort(key=lambda r: r["x_start_m"])
        params["beam_system_mode"] = "Multi-span"
        params["node_positions_m"] = list(node_positions)
        params["support_types"] = list(support_types)
        params["support_positions"] = list(node_positions)
        params["udl_loads_sls"] = [
            {"x_start_m": r["x_start_m"], "x_end_m": r["x_end_m"], "w_kN_per_m": r["w_sls"]} for r in ms_udl_rows
        ]
        params["udl_loads_uls"] = [
            {"x_start_m": r["x_start_m"], "x_end_m": r["x_end_m"], "w_kN_per_m": r["w_uls"]} for r in ms_udl_rows
        ]
    else:
        case_raw = str(
            st.session_state.get("load_case", get_param("sfd_case", _LOADING_OPTIONS_SINGLE[0]) or "")
            or _LOADING_OPTIONS_SINGLE[0]
        ).strip()
        case = case_raw if case_raw in _LOADING_OPTIONS_SINGLE else _LOADING_OPTIONS_SINGLE[0]
        L = float(get_param("L", 3000.0) or 3000.0) / 1000.0
        L = max(L, 0.1)

        is_overhang_case = case == "Overhanging beam – right overhang with point load at free end"
        is_cantilever_case = case.startswith("Cantilever")

        if not is_overhang_case:
            if is_cantilever_case:
                support_condition = "Fixed–Free"
            else:
                support_condition = str(
                    get_param("design_support_condition", "Simply supported") or "Simply supported"
                ).replace("-", "–")
            params["support_condition"] = support_condition

        if case in (
            "Simple beam – UDL over entire span",
            "Simple beam – partial UDL from left (length a)",
            "Cantilever – UDL over entire span",
        ):
            g = float(get_param("g_udl_kNm_per_m", 8.0) or 0.0)
            q = float(get_param("q_udl_kNm_per_m", 4.0) or 0.0)
            psi_shared = float(get_param("psi_udl", 0.4) or 0.4)
            w_sls = g + psi_shared * q
            w_uls = gamma_g * g + gamma_q * q
            if case == "Simple beam – partial UDL from left (length a)":
                a_udl = float(get_param("a_udl_m", L / 2.0) or (L / 2.0))
                params["a_udl"] = _clamp_x(a_udl, float(L))

        elif case in (
            "Simple beam – multiple point loads",
            "Cantilever – multiple point loads",
            "Simple beam – point load at centre",
            "Simple beam – point load at distance a from left",
            "Cantilever – point load at free end",
            "Cantilever – point load at distance a from fixed end",
            "Overhanging beam – right overhang with point load at free end",
        ):
            multi_point_case = case in ("Simple beam – multiple point loads", "Cantilever – multiple point loads")
            psi_shared = float(get_param("psi_point", 0.4) or 0.4)

            if multi_point_case:
                n_point_loads = int(round(float(st.session_state.get("sfd_point_load_count", 2.0) or 2.0)))
                n_point_loads = max(1, min(6, n_point_loads))
                point_load_rows = []
                for i in range(1, n_point_loads + 1):
                    default_x = (i / (n_point_loads + 1.0)) * float(L)
                    g_val = float(st.session_state.get(f"load_G_point_{i}", 50.0) or 50.0)
                    q_val = float(st.session_state.get(f"load_Q_point_{i}", 30.0) or 30.0)
                    x_i = float(st.session_state.get(f"load_x_point_{i}", default_x) or default_x)
                    x_clamped = _clamp_x(x_i, float(L))
                    p_sls_i = g_val + psi_shared * q_val
                    p_uls_i = gamma_g * g_val + gamma_q * q_val
                    point_load_rows.append({"x_m": x_clamped, "P_sls_kN": p_sls_i, "P_uls_kN": p_uls_i})
                point_load_rows.sort(key=lambda row: row["x_m"])
                point_loads_sls = [{"x_m": row["x_m"], "P_kN": row["P_sls_kN"]} for row in point_load_rows]
                point_loads_uls = [{"x_m": row["x_m"], "P_kN": row["P_uls_kN"]} for row in point_load_rows]
                P_sls_total = float(sum(row["P_sls_kN"] for row in point_load_rows))
                P_uls_total = float(sum(row["P_uls_kN"] for row in point_load_rows))
            else:
                G_shared = float(st.session_state.get("load_G_point", get_param("G_point_kN", 50.0) or 50.0))
                Q_shared = float(st.session_state.get("load_Q_point", get_param("Q_point_kN", 30.0) or 30.0))
                P_sls = G_shared + psi_shared * Q_shared
                P_uls = gamma_g * G_shared + gamma_q * Q_shared

                if case == "Simple beam – point load at distance a from left":
                    params["a"] = _clamp_x(float(get_param("a_m", L / 3.0) or (L / 3.0)), float(L))
                elif case == "Cantilever – point load at distance a from fixed end":
                    params["a_cant"] = _clamp_x(float(get_param("a_cant_m", L / 2.0) or (L / 2.0)), float(L))
                elif case == "Overhanging beam – right overhang with point load at free end":
                    params["L_main"] = float(L)
                    params["a_overhang"] = float(get_param("a_overhang_m", 2.0) or 2.0)

    params_uls = dict(params)
    params_sls = dict(params)
    if w_sls is not None and w_uls is not None:
        params_uls["w"] = float(w_uls)
        params_sls["w"] = float(w_sls)
    if P_sls is not None and P_uls is not None:
        params_uls["P"] = float(P_uls)
        params_sls["P"] = float(P_sls)
    if point_loads_sls is not None and point_loads_uls is not None:
        params_uls["point_loads"] = point_loads_uls
        params_sls["point_loads"] = point_loads_sls
    if "udl_loads_uls" in params and "udl_loads_sls" in params:
        params_uls["udl_loads"] = list(params.get("udl_loads_uls") or [])
        params_sls["udl_loads"] = list(params.get("udl_loads_sls") or [])

    x_uls, V_uls_vals, M_uls_vals, beam_length_uls, results_local_uls = _compute_diagram_arrays(
        case, L, params_uls
    )
    x_sls, V_sls_vals, M_sls_vals, beam_length_sls, _results_local_sls = _compute_diagram_arrays(
        case, L, params_sls
    )

    V_uls = float(np.max(np.abs(V_uls_vals))) if V_uls_vals is not None else 0.0
    M_uls = float(np.max(np.abs(M_uls_vals))) if M_uls_vals is not None else 0.0
    V_sls = float(np.max(np.abs(V_sls_vals))) if V_sls_vals is not None else 0.0
    M_sls = float(np.max(np.abs(M_sls_vals))) if M_sls_vals is not None else 0.0
    M_pos_max_uls = float(max(0.0, float(np.max(M_uls_vals)))) if M_uls_vals is not None else 0.0
    M_neg_min_uls = float(min(0.0, float(np.min(M_uls_vals)))) if M_uls_vals is not None else 0.0
    M_pos_max_sls = float(max(0.0, float(np.max(M_sls_vals)))) if M_sls_vals is not None else 0.0
    M_neg_min_sls = float(min(0.0, float(np.min(M_sls_vals)))) if M_sls_vals is not None else 0.0

    if V_uls_vals is not None and len(V_uls_vals) and x_uls is not None and len(x_uls):
        _crit_idx = int(np.argmax(np.abs(V_uls_vals)))
        x_crit = float(x_uls[_crit_idx])
        V_crit = float(V_uls_vals[_crit_idx])
    else:
        x_crit = None
        V_crit = None

    support_type_resolved = _defl_support_type_from_selection(
        case, str(params_sls.get("support_condition", "") or "")
    )
    support_type_key = "cantilever" if support_type_resolved == "Cantilever" else "simply_supported"

    x_uls_list = [float(v) for v in (x_uls.tolist() if hasattr(x_uls, "tolist") else list(x_uls))]
    xu = np.asarray(x_uls_list, dtype=float)
    Mu = np.asarray(
        M_uls_vals.tolist() if hasattr(M_uls_vals, "tolist") else list(M_uls_vals or []),
        dtype=float,
    )
    xs = np.asarray(x_sls.tolist() if hasattr(x_sls, "tolist") else list(x_sls or []), dtype=float)
    Ms = np.asarray(
        M_sls_vals.tolist() if hasattr(M_sls_vals, "tolist") else list(M_sls_vals or []),
        dtype=float,
    )
    if xu.size >= 2 and Mu.size == xu.size and Ms.size == xs.size:
        if xs.shape == xu.shape and float(np.max(np.abs(xs - xu))) <= 1e-6 * max(1.0, float(xu[-1])):
            M_sls_on_xu = Ms
        else:
            M_sls_on_xu = np.interp(xu, xs, Ms, left=float(Ms[0]), right=float(Ms[-1]))
    else:
        M_sls_on_xu = np.array([], dtype=float)

    sup_pos = [float(v) for v in (results_local_uls.get("support_positions") or [])]
    sup_types = [str(v) for v in (results_local_uls.get("support_types") or [])]
    if not sup_types and len(sup_pos) >= 2:
        sup_types = ["Pinned", "Roller"]
    elif not sup_types and len(sup_pos) == 1:
        sup_types = ["Fixed"]

    V_uls_vals_arr = np.asarray(V_uls_vals, dtype=float) if V_uls_vals is not None else np.array([], dtype=float)
    moment_x = [float(v) for v in x_uls_list]
    moment_vals = [float(v) for v in M_sls_on_xu.tolist()] if M_sls_on_xu.size == xu.size else []

    _fp = diagram_cache_fingerprint(
        str(case),
        float(beam_length_uls),
        dict(params_uls or {}),
        float(beam_length_sls),
        dict(params_sls or {}),
    )

    update_results(
        sfd_case=case,
        sfd_Msls_max_kNm=float(M_sls),
        sfd_Vsls_max_kN=float(V_sls),
        sfd_Mmax_abs_kNm=float(M_uls),
        sfd_Vmax_abs_kN=float(V_uls),
        M_pos_max_uls_kNm=float(M_pos_max_uls),
        M_neg_min_uls_kNm=float(M_neg_min_uls),
        M_pos_max_sls_kNm=float(M_pos_max_sls),
        M_neg_min_sls_kNm=float(M_neg_min_sls),
        shear_x=moment_x,
        shear_V=[float(abs(v)) for v in V_uls_vals_arr.tolist()],
        shear_V_signed=[float(v) for v in V_uls_vals_arr.tolist()],
        shear_M_uls_kNm=[float(v) for v in Mu.tolist()],
        shear_M_sls_kNm=moment_vals,
        moment_x=moment_x,
        moment_values=moment_vals,
        crack_bmd_cache_fingerprint=_fp,
        bmd_support_positions_m=sup_pos,
        bmd_support_types=sup_types,
        support_type=support_type_key,
        critical_shear_x=x_crit,
        critical_shear_V=V_crit,
        V_max=float(np.max(np.abs(V_uls_vals_arr))) if V_uls_vals_arr.size else 0.0,
    )
