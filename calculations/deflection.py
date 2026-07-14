from __future__ import annotations

import math

from calculations.materials import derive_concrete_modulus_from_fc


SUPPORT_DEFLECTION_MAP = {
    "Simply supported": {"k2": 5.0 / 384.0, "diagram": "simply_supported_udl"},
    "Pinned–Pinned": {"k2": 5.0 / 384.0, "diagram": "simply_supported_udl"},
    "Continuous – end span": {"k2": 2.4 / 384.0, "diagram": "continuous_span_udl"},
    "Continuous – interior span": {
        "k2": 1.5 / 384.0,
        "diagram": "continuous_span_udl",
    },
    "Fixed-ended": {"k2": 1.0 / 384.0, "diagram": "fixed_fixed_udl"},
    "Fixed–Pinned": {"k2": 1.0 / 185.0, "diagram": "fixed_pinned_udl"},
    "Pinned–Fixed": {"k2": 1.0 / 185.0, "diagram": "fixed_pinned_udl"},
    "Cantilever": {"k2": 1.0 / 8.0, "diagram": "cantilever_udl"},
}

DEFLECTION_SUPPORT_OPTIONS_BASE = [
    "Simply supported",
    "Pinned–Pinned",
    "Continuous – end span",
    "Continuous – interior span",
    "Cantilever",
]

DEFLECTION_LIMIT_OPTIONS = {
    "L/150": 150,
    "L/180": 180,
    "L/250": 250,
    "L/300": 300,
    "L/350": 350,
    "L/500": 500,
}
DEFLECTION_LIMIT_DEFAULT_LABEL = "L/250"
DEFLECTION_LIMIT_DEFAULT_RATIO = DEFLECTION_LIMIT_OPTIONS[DEFLECTION_LIMIT_DEFAULT_LABEL]

DEFLECTION_LIMIT_HELP_TEXT = (
    "Select the serviceability deflection limit required for the member and project. "
    "AS/NZS 1170.0 Appendix C provides general guidance on deformation and deflection limits, "
    "but it does not prescribe one universal fixed limit for every case. "
    "The adopted limit should reflect the governing serviceability requirement and may depend on "
    "the relevant material code, project specification, finishes, partitions, glazing, "
    "appearance criteria, client requirements, and engineering judgement."
)


def get_deflection_limit_ratio(value) -> int:
    """Canonical deflection limit ratio (fallback to default when invalid/unsupported)."""
    try:
        ratio = int(round(float(value)))
    except Exception:
        return int(DEFLECTION_LIMIT_DEFAULT_RATIO)
    if ratio in DEFLECTION_LIMIT_OPTIONS.values():
        return ratio
    return int(DEFLECTION_LIMIT_DEFAULT_RATIO)


def get_deflection_limit_label_from_ratio(value) -> str:
    ratio = get_deflection_limit_ratio(value)
    for label, r in DEFLECTION_LIMIT_OPTIONS.items():
        if int(r) == int(ratio):
            return label
    return DEFLECTION_LIMIT_DEFAULT_LABEL


def get_deflection_limit_ratio_from_label(label: str) -> int:
    return int(DEFLECTION_LIMIT_OPTIONS.get(label, DEFLECTION_LIMIT_DEFAULT_RATIO))


def format_deflection_allowable_limit_mm(defl_limit_mm: float, defl_limit_ratio: float) -> str:
    ratio = get_deflection_limit_ratio(defl_limit_ratio)
    ratio_label = get_deflection_limit_label_from_ratio(ratio)
    if defl_limit_mm and defl_limit_mm > 0:
        return f"δlim = {defl_limit_mm:.2f} mm ({ratio_label})"
    return "—"


def format_L_over_delta(delta_mm, L_mm):
    if delta_mm <= 0:
        return "–"
    ratio = L_mm / delta_mm
    if ratio <= 0:
        return "–"
    return f"L/{ratio:,.0f}"


def effective_flexural_rigidity_kNm2(Ec_mpa: float, Ief_mm4: float) -> float:
    """Effective flexural rigidity for the beam solver in kN.m^2."""
    return max(float(Ec_mpa) * float(Ief_mm4) / 1e9, 1e-12)


def span_deflection_utilisation_values(
    *,
    delta_abs_mm: float,
    span_len_m: float,
    ratio: float,
) -> dict[str, float]:
    """Deflection limit and utilisation for one span."""
    limit_mm = (float(span_len_m) * 1000.0) / float(ratio)
    util = (float(delta_abs_mm) / limit_mm) if limit_mm > 0 else 0.0
    return {
        "limit_mm": limit_mm,
        "util": util,
    }


def derive_effective_concrete_modulus(Ec_mpa: float, phi_cc_t: float) -> float:
    """
    Long-term effective modulus used in deflection/crack stiffness context.
    Consistent with n_e = (1 + phi_cc_t) * Es / Ec => Eceff = Ec / (1 + phi_cc_t).
    """
    Ec_safe = max(1e-9, float(Ec_mpa or 0.0))
    phi_safe = max(0.0, float(phi_cc_t or 0.0))
    return float(Ec_safe / (1.0 + phi_safe))


def derive_sustained_stress_ratio(
    *,
    fc_mpa: float,
    sls_m_pos_kNm: float,
    sls_m_neg_kNm: float,
    z_top_mm3: float,
    z_bot_mm3: float,
) -> dict:
    """
    Derive sustained concrete stress ratio from the governing sustained SLS moment.
    sigma_cs = M_sust / Z_comp (MPa), stress_ratio = sigma_cs / f'c.
    """
    fc_safe = max(0.0, float(fc_mpa or 0.0))
    m_pos = max(0.0, float(sls_m_pos_kNm or 0.0))
    m_neg = max(0.0, float(sls_m_neg_kNm or 0.0))
    use_sagging = m_pos >= m_neg
    m_sust = m_pos if use_sagging else m_neg
    z_comp = float((z_top_mm3 if use_sagging else z_bot_mm3) or 0.0)
    sigma_cs = (m_sust * 1.0e6 / z_comp) if (m_sust > 0.0 and z_comp > 0.0) else 0.0
    ratio = (sigma_cs / fc_safe) if fc_safe > 0.0 else 0.0
    return {
        "stress_ratio": float(max(0.0, ratio)),
        "sigma_cs_mpa": float(max(0.0, sigma_cs)),
        "M_sust_kNm": float(max(0.0, m_sust)),
        "Z_comp_mm3": float(max(0.0, z_comp)),
        "compression_fibre": "top" if use_sagging else "bottom",
    }


def support_props(support_type: str) -> dict:
    return SUPPORT_DEFLECTION_MAP.get(
        support_type,
        SUPPORT_DEFLECTION_MAP["Simply supported"],
    )


def _support_label_words(value: str | None) -> list[str]:
    raw = str(value or "").strip().lower()
    for sep in ("-", "–", "�", "_", "/"):
        raw = raw.replace(sep, " ")
    return [part for part in raw.split() if part]


def _support_label_from_words(value: str | None) -> str | None:
    words = _support_label_words(value)
    if not words:
        return None
    joined = " ".join(words)
    if "cantilever" in words or ("fixed" in words and "free" in words):
        return "Cantilever"
    if "continuous" in words:
        return "Continuous � interior span"
    if "simply" in words:
        return "Simply supported"
    if words.count("fixed") >= 2:
        return "Fixed-ended"
    if words.count("pinned") >= 2:
        return "Pinned�Pinned"
    if "fixed" in words and "pinned" in words:
        return "Fixed�Pinned" if joined.index("fixed") < joined.index("pinned") else "Pinned�Fixed"
    return None


def normalize_deflection_support_type(value: str | None) -> str:
    parsed = _support_label_from_words(value)
    if parsed is not None:
        return parsed
    raw = (value or "").strip().replace("-", "�")
    if raw == "Fixed�ended":
        raw = "Fixed-ended"
    if raw in SUPPORT_DEFLECTION_MAP:
        return raw
    raw_low = raw.lower()
    if "cantilever" in raw_low or raw == "Fixed�Free":
        return "Cantilever"
    if raw == "Fixed-ended" or "fixed-ended" in raw_low:
        return "Fixed-ended"
    if "fixed�pinned" in raw_low or "fixed-pinned" in raw_low:
        return "Fixed�Pinned"
    if "pinned�fixed" in raw_low or "pinned-fixed" in raw_low:
        return "Pinned�Fixed"
    if "fixed�fixed" in raw_low or "fixed-fixed" in raw_low:
        return "Fixed-ended"
    if "continuous" in raw_low:
        return "Continuous � interior span"
    if raw_low in ("pinned�pinned", "pinned-pinned"):
        return "Pinned�Pinned"
    if "simply" in raw_low:
        return "Simply supported"
    if "pinned" in raw_low:
        return "Simply supported"
    return "Simply supported"

def support_type_from_sfd_case(case: str) -> str:
    case = (case or "").strip()
    if case.startswith("Cantilever"):
        return "Cantilever"
    if case.startswith("Simple beam"):
        return "Simply supported"
    if case.startswith("Overhanging beam"):
        return "Simply supported"
    return "Simply supported"


def defl_support_type_from_design_selection(
    load_case: str | None,
    support_condition: str | None,
) -> str:
    """
    Match sfd_bmd_page._defl_support_type_from_selection for single-span design.
    """
    case_text = (load_case or "").strip()
    parsed = _support_label_from_words(support_condition)
    cond = (support_condition or "").strip().replace("-", "�")
    if case_text == "Overhanging beam � right overhang with point load at free end":
        return "Simply supported"
    if parsed == "Cantilever" or cond == "Fixed�Free" or case_text.startswith("Cantilever"):
        return "Cantilever"
    if parsed is not None:
        return parsed
    if cond == "Simply supported":
        return "Simply supported"
    if cond == "Pinned�Pinned":
        return "Pinned�Pinned"
    if cond == "Fixed�Fixed":
        return "Fixed-ended"
    if cond == "Fixed�Pinned":
        return "Fixed�Pinned"
    if cond == "Pinned�Fixed":
        return "Pinned�Fixed"
    return support_type_from_sfd_case(case_text)

def deflection_support_options_for_value(resolved: str) -> list[str]:
    opts = list(DEFLECTION_SUPPORT_OPTIONS_BASE)
    if resolved in SUPPORT_DEFLECTION_MAP and resolved not in opts:
        opts = opts + [resolved]
    return opts


def design_multispan_mode_from_state(
    state: dict,
    actions_mode_default: str = "manual",
) -> bool:
    """True when the design/SFD state represents a multi-span deflection model."""
    mode = str(state.get("actions_mode", actions_mode_default) or "manual").strip().lower()
    beam_mode = str(state.get("sfd_beam_system_mode", "") or "").strip()
    case_text = str(state.get("sfd_case", "") or "").strip()
    return mode == "design" and (
        beam_mode == "Multi-span" or case_text.startswith("Multi-span continuous beam")
    )


def active_multispan_lengths_m(state: dict) -> list[float]:
    """Active multi-span lengths in metres, preserving the page's zero fallback."""
    lengths: list[float] = []
    try:
        n_spans = int(float(state.get("sfd_span_count", 0.0) or 0.0))
    except Exception:
        n_spans = 0
    for i in range(1, n_spans + 1):
        try:
            li = float(state.get(f"sfd_span_len_{i}", 0.0) or 0.0)
        except Exception:
            li = 0.0
        lengths.append(max(0.0, li))
    return lengths


def multispan_design_elastic_loads(
    source: dict,
    *,
    psi_point_default: float = 0.4,
    psi_udl_default: float = 0.4,
) -> tuple[list[float], list[str], list[dict], list[dict], list[dict], list[dict]]:
    """Characteristic and sustained SLS loads for the design multi-span model."""
    n_spans = int(float(source.get("sfd_span_count", 0.0) or 0.0))
    node_positions_m: list[float] = [0.0]
    for i in range(1, n_spans + 1):
        li = float(source.get(f"sfd_span_len_{i}", 0.0) or 0.0)
        node_positions_m.append(node_positions_m[-1] + max(0.0, li))
    support_types = [
        str(source.get(f"sfd_support_type_{j}", "Pinned") or "Pinned")
        for j in range(1, n_spans + 2)
    ]
    L_tot = float(node_positions_m[-1]) if node_positions_m else 0.0
    psi_point = float(source.get("load_psi_point", psi_point_default) or 0.4)
    psi_udl = float(source.get("load_psi_udl", psi_udl_default) or 0.4)
    n_point = int(float(source.get("sfd_ms_point_count", 0.0) or 0.0))
    pl_char: list[dict] = []
    pl_sust: list[dict] = []
    for i in range(1, max(0, n_point) + 1):
        G = float(source.get(f"load_ms_G_{i}", 0.0) or 0.0)
        Q = float(source.get(f"load_ms_Q_{i}", 0.0) or 0.0)
        x = float(source.get(f"load_ms_x_{i}", 0.0) or 0.0)
        x = max(node_positions_m[0], min(L_tot, x))
        pl_char.append({"x_m": x, "P_kN": G + Q})
        pl_sust.append({"x_m": x, "P_kN": G + psi_point * Q})
    n_udl = int(float(source.get("sfd_ms_udl_count", 0.0) or 0.0))
    udl_char: list[dict] = []
    udl_sust: list[dict] = []
    for i in range(1, max(0, n_udl) + 1):
        g = float(source.get(f"load_ms_g_{i}", 0.0) or 0.0)
        q = float(source.get(f"load_ms_q_{i}", 0.0) or 0.0)
        x0 = float(source.get(f"load_ms_x0_{i}", 0.0) or 0.0)
        x1 = float(source.get(f"load_ms_x1_{i}", L_tot) or 0.0)
        x0 = max(node_positions_m[0], min(L_tot, x0))
        x1 = max(node_positions_m[0], min(L_tot, x1))
        if x1 <= x0:
            continue
        udl_char.append({"x_start_m": x0, "x_end_m": x1, "w_kN_per_m": g + q})
        udl_sust.append({"x_start_m": x0, "x_end_m": x1, "w_kN_per_m": g + psi_udl * q})
    return node_positions_m, support_types, pl_char, udl_char, pl_sust, udl_sust


def multispan_deflection_metric_values(
    *,
    state: dict,
    Ec: float,
    Ief: float,
    g_kNm: float,
    q_kNm: float,
    psi_s: float,
    defl_limit_ratio: float,
    Ast: float = 0.0,
    Asc: float = 0.0,
    actions_mode_default: str = "manual",
    psi_point_default: float = 0.4,
    psi_udl_default: float = 0.4,
    solve_beam_structure_fn=None,
) -> dict:
    """Multi-span deflection metrics without mutating Streamlit/session state."""
    source = dict(state or {})

    if not design_multispan_mode_from_state(
        source,
        actions_mode_default=actions_mode_default,
    ):
        return {"available": False, "reason": "not design multispan mode"}

    span_lengths = active_multispan_lengths_m(source)
    if len(span_lengths) < 2:
        return {"available": False, "reason": "insufficient active spans"}

    try:
        ratio = float(get_deflection_limit_ratio(defl_limit_ratio))
    except Exception:
        ratio = 250.0
    if ratio <= 0:
        ratio = 250.0

    n_spans = len(span_lengths)
    span_g_inputs: list[float] = []
    span_q_inputs: list[float] = []
    for i in range(1, n_spans + 1):
        try:
            span_g_inputs.append(float(source.get(f"load_ms_g_{i}", 0.0) or 0.0))
        except Exception:
            span_g_inputs.append(0.0)
        try:
            span_q_inputs.append(float(source.get(f"load_ms_q_{i}", 0.0) or 0.0))
        except Exception:
            span_q_inputs.append(0.0)

    g_fallback = float(g_kNm)
    q_fallback = float(q_kNm)

    span_deflections_mm: list[float] = []
    span_utilisations: list[float] = []
    metrics_source = "multispan_fem_elastic"
    used_solver = False

    try:
        if solve_beam_structure_fn is not None:
            node_positions_m, support_types_ms, pl_c, udl_c, pl_s, udl_s = (
                multispan_design_elastic_loads(
                    source,
                    psi_point_default=psi_point_default,
                    psi_udl_default=psi_udl_default,
                )
            )
            if len(node_positions_m) >= 2 and len(support_types_ms) == len(node_positions_m):
                ei_knm2 = effective_flexural_rigidity_kNm2(Ec, Ief)
                res_c = solve_beam_structure_fn(
                    node_positions_m,
                    support_types_ms,
                    pl_c,
                    udl_c,
                    n_points_per_span=96,
                    ei_knm2_for_deflection=ei_knm2,
                )
                res_s = solve_beam_structure_fn(
                    node_positions_m,
                    support_types_ms,
                    pl_s,
                    udl_s,
                    n_points_per_span=96,
                    ei_knm2_for_deflection=ei_knm2,
                )
                w_c = res_c.get("w_mm")
                w_s = res_s.get("w_mm")
                x_sol = res_c.get("x")
                if (
                    isinstance(w_c, list)
                    and isinstance(w_s, list)
                    and isinstance(x_sol, list)
                    and len(w_c) == len(w_s) == len(x_sol)
                    and len(w_c) > 0
                ):
                    kcs_line = deflection_sustained_load_factor(Asc, Ast)
                    delta_line_mm = [
                        -float(wc) + kcs_line * -float(ws)
                        for wc, ws in zip(w_c, w_s)
                    ]
                    span_deflections_mm = []
                    span_utilisations = []
                    for idx, span_len_m in enumerate(span_lengths):
                        if span_len_m <= 0:
                            span_deflections_mm.append(0.0)
                            span_utilisations.append(0.0)
                            continue
                        x_left = float(node_positions_m[idx])
                        x_right = float(node_positions_m[idx + 1])
                        span_values = [
                            abs(delta)
                            for x_val, delta in zip(x_sol, delta_line_mm)
                            if float(x_val) >= x_left - 1e-9
                            and float(x_val) <= x_right + 1e-9
                        ]
                        if not span_values:
                            span_deflections_mm.append(0.0)
                            span_utilisations.append(0.0)
                            continue
                        delta_abs = float(max(span_values))
                        span_limit = span_deflection_utilisation_values(
                            delta_abs_mm=delta_abs,
                            span_len_m=span_len_m,
                            ratio=ratio,
                        )
                        span_deflections_mm.append(delta_abs)
                        span_utilisations.append(span_limit["util"])
                    used_solver = True
    except Exception:
        used_solver = False
        metrics_source = "multispan_fem_elastic_failed"

    if not used_solver:
        metrics_source = "per_span_k2_approx"
        span_deflections_mm = []
        span_utilisations = []
        for idx, span_len_m in enumerate(span_lengths):
            if span_len_m <= 0:
                span_deflections_mm.append(0.0)
                span_utilisations.append(0.0)
                continue

            span_support = (
                "Continuous â€“ end span"
                if idx in (0, n_spans - 1)
                else "Continuous â€“ interior span"
            )
            try:
                g_i = float(span_g_inputs[idx])
            except Exception:
                g_i = 0.0
            try:
                q_i = float(span_q_inputs[idx])
            except Exception:
                q_i = 0.0
            if (g_i + q_i) == 0.0 and (g_fallback + q_fallback) > 0.0:
                g_i, q_i = g_fallback, q_fallback

            calc = calc_deflection_as3600(
                L_m=float(span_len_m),
                Ec=float(Ec),
                Ief=float(Ief),
                g_kNm=g_i,
                q_kNm=q_i,
                psi_s=float(psi_s),
                support_type=span_support,
                Ast=float(Ast),
                Asc=float(Asc),
            )
            if isinstance(calc, dict) and not calc.get("ok", True):
                span_deflections_mm.append(0.0)
                span_utilisations.append(0.0)
                continue

            delta_abs = abs(float(calc.get("delta_total", 0.0) or 0.0))
            span_limit = span_deflection_utilisation_values(
                delta_abs_mm=delta_abs,
                span_len_m=span_len_m,
                ratio=ratio,
            )
            span_deflections_mm.append(delta_abs)
            span_utilisations.append(span_limit["util"])

    return {
        "available": True,
        "span_deflections_mm": span_deflections_mm,
        "span_utilisations": span_utilisations,
        "metrics_source": metrics_source,
    }


def pick_controlling_span_index(state: dict) -> tuple[int, str]:
    """
    Deterministic controlling-span selector:
    1) max utilisation, 2) max deflection magnitude, 3) longest active span, 4) first span.
    """
    vals = state.get("defl_span_utilisations")
    if isinstance(vals, (list, tuple)) and vals:
        nums = []
        for i, v in enumerate(vals):
            try:
                nums.append((i, abs(float(v))))
            except Exception:
                pass
        if nums:
            idx = max(nums, key=lambda item: item[1])[0]
            return idx, "highest deflection utilisation"

    vals = state.get("defl_span_deflections_mm")
    if isinstance(vals, (list, tuple)) and vals:
        nums = []
        for i, v in enumerate(vals):
            try:
                nums.append((i, abs(float(v))))
            except Exception:
                pass
        if nums:
            idx = max(nums, key=lambda item: item[1])[0]
            return idx, "largest absolute deflection"

    span_lengths = []
    try:
        n_spans = int(float(state.get("sfd_span_count", 0.0) or 0.0))
    except Exception:
        n_spans = 0
    for i in range(1, n_spans + 1):
        try:
            li = float(state.get(f"sfd_span_len_{i}", 0.0) or 0.0)
        except Exception:
            li = 0.0
        span_lengths.append(max(0.0, li))
    if span_lengths:
        idx = max(range(len(span_lengths)), key=lambda i: span_lengths[i])
        return int(idx), "longest active span"

    return 0, "fallback"


def governing_span_support_pair(state: dict, support_resolution: dict) -> tuple[str, str] | None:
    try:
        if str(support_resolution.get("mode", "")).strip().lower() != "design":
            return None
        if not bool(support_resolution.get("multi_span")):
            return None
        n_spans = int(float(state.get("sfd_span_count", 0.0) or 0.0))
        if n_spans < 1:
            return None
        idx = int(support_resolution.get("controlling_span_idx", 0) or 0)
        idx = max(0, min(idx, n_spans - 1))
        left_i = idx + 1
        right_i = idx + 2
        left = str(state.get(f"sfd_support_type_{left_i}", "Pinned") or "Pinned")
        right = str(state.get(f"sfd_support_type_{right_i}", "Pinned") or "Pinned")
        return (left, right)
    except Exception:
        return None


def derive_equiv_udl_from_actions(M_kNm, V_kN, L_m, support_type):
    """
    Derive equivalent full-span UDL (kN/m) from M* and/or V*.
    Accept zeros; only None is treated as missing.
    """
    note_parts = []
    if L_m is None:
        return {
            "w_kN_per_m": None,
            "w_from_M": None,
            "w_from_V": None,
            "consistent": None,
            "note": "L_m missing",
        }
    try:
        L_m = float(L_m)
    except Exception:
        return {
            "w_kN_per_m": None,
            "w_from_M": None,
            "w_from_V": None,
            "consistent": None,
            "note": "L_m not numeric",
        }
    if not math.isfinite(L_m):
        return {
            "w_kN_per_m": None,
            "w_from_M": None,
            "w_from_V": None,
            "consistent": None,
            "note": "L_m not finite",
        }
    if L_m > 50:
        note_parts.append(
            f"WARNING: L_m={L_m} looks like mm, not m (expected ~0–50)."
        )
        return {
            "w_kN_per_m": None,
            "w_from_M": None,
            "w_from_V": None,
            "consistent": None,
            "note": " ".join(note_parts),
        }
    if L_m <= 0:
        return {
            "w_kN_per_m": None,
            "w_from_M": None,
            "w_from_V": None,
            "consistent": None,
            "note": "L_m must be > 0",
        }

    support = (support_type or "").strip()
    if support == "Cantilever":
        aM, aV = 2.0, 1.0
        cons_M = lambda V: (V * L_m / 2.0)
    else:
        aM, aV = 8.0, 2.0
        cons_M = lambda V: (V * L_m / 4.0)

    wM = None
    wV = None
    if M_kNm is not None and math.isfinite(float(M_kNm)):
        M_abs = abs(float(M_kNm))
        wM = aM * M_abs / (L_m**2)
    if V_kN is not None and math.isfinite(float(V_kN)):
        V_abs = abs(float(V_kN))
        wV = aV * V_abs / L_m

    if wM is None and wV is None:
        return {
            "w_kN_per_m": None,
            "w_from_M": None,
            "w_from_V": None,
            "consistent": None,
            "note": "No M or V provided",
        }
    if wM is None:
        return {
            "w_kN_per_m": wV,
            "w_from_M": None,
            "w_from_V": wV,
            "consistent": None,
            "note": "Derived from V only",
        }
    if wV is None:
        return {
            "w_kN_per_m": wM,
            "w_from_M": wM,
            "w_from_V": None,
            "consistent": None,
            "note": "Derived from M only",
        }

    M_implied = cons_M(abs(float(V_kN)))
    M_provided = abs(float(M_kNm))
    if M_implied > 0:
        ratio = M_provided / M_implied
        consistent = 0.85 <= ratio <= 1.15
    else:
        ratio = None
        consistent = None

    if ratio is not None:
        note_parts.append(
            f"M/V UDL consistency ratio = {ratio:.2f} (≈1 means consistent full-span UDL)."
        )

    if consistent is True:
        w = 0.5 * (wM + wV)
        note_parts.append("M and V consistent → using average(wM, wV).")
    else:
        w = max(wM, wV)
        note_parts.append(
            "M and V not consistent with full-span UDL → using max(wM, wV) (conservative)."
        )

    return {
        "w_kN_per_m": w,
        "w_from_M": wM,
        "w_from_V": wV,
        "consistent": consistent,
        "note": " ".join(note_parts),
    }


def has_udl_line_loads(g_udl: float | None, q_udl: float | None) -> bool:
    """True when explicit dead + live line UDLs (kN/m) sum to a positive value."""
    return float(g_udl or 0.0) + float(q_udl or 0.0) > 0.0


def resolve_deflection_equiv_loads_from_inputs(
    *,
    derived: dict,
    w_sls: float | None,
    g_udl: float | None,
    q_udl: float | None,
) -> tuple[float, float]:
    """
    Map SLS-derived / stored UDL inputs to (g_equiv, q_equiv) for calc_deflection_as3600.

    ``derived`` must be the dict from ``derive_equiv_udl_from_actions`` for the same inputs.
    """
    if derived["w_kN_per_m"] is not None:
        w_used = float(derived["w_kN_per_m"])
    elif w_sls is not None:
        w_used = float(w_sls)
    else:
        w_used = float((g_udl or 0.0) + (q_udl or 0.0))

    if w_used > 0:
        if g_udl is not None and q_udl is not None and (float(g_udl) + float(q_udl)) > 0:
            g_ratio = float(g_udl) / float(float(g_udl) + float(q_udl))
            g_equiv = w_used * g_ratio
            q_equiv = w_used * (1.0 - g_ratio)
        else:
            g_equiv = w_used
            q_equiv = 0.0
    else:
        g_equiv = float(g_udl or 0.0)
        q_equiv = float(q_udl or 0.0)
    return g_equiv, q_equiv


def deflection_multispan_load_split_values(
    *,
    derived: dict,
    g_kNm: float | None,
    q_kNm: float | None,
) -> dict[str, float | str | None]:
    """Legacy page split of equivalent service load into g/q components."""
    if derived["w_kN_per_m"] is not None:
        w_used = derived["w_kN_per_m"]
        w_source = "actions"
    else:
        w_used = (g_kNm + q_kNm) if (g_kNm is not None and q_kNm is not None) else 0.0
        w_source = "g+q"

    if w_used > 0:
        if (g_kNm + q_kNm) > 0:
            g_ratio = g_kNm / (g_kNm + q_kNm)
            g_used = w_used * g_ratio
            q_used = w_used * (1 - g_ratio)
        else:
            g_used = w_used
            q_used = 0.0
    else:
        g_used = g_kNm
        q_used = q_kNm

    return {
        "w_used": w_used,
        "w_source": w_source,
        "g_used": g_used,
        "q_used": q_used,
    }


def effective_design_load_from_shear(
    *,
    V_kN: float | None,
    L_m: float | None,
    support_type: str | None,
) -> tuple[float | None, str | None]:
    """
    Derive F_d,ef from shear and span for span/depth checks.

    Simply supported and pinned-pinned spans use 2V/L; other supported cases use V/L.
    """
    try:
        V = float(V_kN) if V_kN is not None else None
        L = float(L_m) if L_m is not None else None
    except Exception:
        return None, None
    if V is None or L is None or V <= 0.0 or L <= 0.0:
        return None, None
    support = str(support_type or "").strip()
    if support in ("Simply supported", "Pinned-Pinned", "Pinnedâ€“Pinned"):
        return 2.0 * V / L, "2V/L"
    return V / L, "V/L"


def deflection_from_sfd_case(
    case: str,
    L: float,
    w_eff: float | None,
    P_sls: float | None,
    E: float,
    I: float,
):
    """
    Returns (delta_max, latex_formula, location_text) for classic SLS load cases.

    Assumes:
      - L in your length unit
      - w_eff in force/length
      - P_sls in force
      - E, I consistent with your deflection units
    """
    delta_max = None
    formula = r"\text{No closed-form deflection linked for this case yet.}"
    location = "—"

    if case == "Simple beam – UDL over entire span" and w_eff is not None:
        delta_max = 5.0 * w_eff * L**4 / (384.0 * E * I)
        formula = (
            r"\delta_{\max} = \frac{5 w L^4}{384 E I}"
            r"\quad\text{(simply supported, full UDL, midspan)}"
        )
        location = "At midspan (x = L/2)"

    elif case == "Simple beam – point load at centre" and P_sls is not None:
        delta_max = P_sls * L**3 / (48.0 * E * I)
        formula = (
            r"\delta_{\max} = \frac{P L^3}{48 E I}"
            r"\quad\text{(simply supported, centre point load)}"
        )
        location = "At midspan (x = L/2)"

    elif case == "Cantilever – point load at free end" and P_sls is not None:
        delta_max = P_sls * L**3 / (3.0 * E * I)
        formula = (
            r"\delta_{\max} = \frac{P L^3}{3 E I}"
            r"\quad\text{(cantilever, end point load)}"
        )
        location = "At free end (x = L)"

    elif case == "Cantilever – UDL over entire span" and w_eff is not None:
        delta_max = w_eff * L**4 / (8.0 * E * I)
        formula = (
            r"\delta_{\max} = \frac{w L^4}{8 E I}"
            r"\quad\text{(cantilever, full UDL)}"
        )
        location = "At free end (x = L)"

    return delta_max, formula, location


def effective_flange_width_ratio(beff: float, bw: float | None) -> float:
    """Effective flange/web width ratio beta with the legacy bw fallback."""
    return float(beff) / float(bw) if (bw is not None and bw > 0) else 1.0


def tension_reinforcement_ratio(Ast: float, beff: float | None, d: float | None) -> float:
    """Tension reinforcement ratio p = Ast / (beff d) with legacy zero fallback."""
    denom = float(beff) * float(d) if (beff is not None and d is not None) else 0.0
    return float(Ast) / denom if denom > 0.0 else 0.0


def calc_ief_simplified(fc, beff, bw, d, Ast):
    """
    AS 3600:2018 Cl. 8.5.3.1(2),(3) simplified Ief for reinforced members.
    """
    beff = max(beff, 1.0)
    bw = max(bw, 1.0)
    d = max(d, 1.0)
    fc = max(fc, 1.0)

    beta = effective_flange_width_ratio(beff, bw)
    p = tension_reinforcement_ratio(Ast, beff, d)
    p_lim = 0.001 * (fc ** (1.0 / 3.0)) / (beta ** (2.0 / 3.0))
    k1 = simplified_ief_k1_factor(fc, beta, p, p_lim)

    if p >= p_lim:
        ief = k1 * beff * (d**3)
        ief_max = (0.1 / (beta ** (2.0 / 3.0))) * beff * (d**3)
    else:
        ief = k1 * beff * (d**3)
        ief_max = (0.06 / (beta ** (2.0 / 3.0))) * beff * (d**3)

    ief = min(ief, ief_max)
    return max(ief, 0.0), beta, p, p_lim, max(ief_max, 0.0), max(k1, 0.0)


def simplified_ief_k1_factor(fc: float, beta: float, p: float, p_lim: float) -> float:
    """Raw simplified-Ief k1 factor before final non-negative display clamp."""
    fc_f = float(fc or 0.0)
    beta_f = max(float(beta or 0.0), 1e-12)
    p_f = float(p or 0.0)
    p_lim_f = float(p_lim or 0.0)
    if p_f >= p_lim_f:
        return (5.0 - 0.04 * fc_f) * p_f + 0.002
    return (0.055 * (fc_f ** (1.0 / 3.0)) / (beta_f ** (2.0 / 3.0))) - 50.0 * p_f


def compression_to_tension_steel_ratio(Asc: float, Ast: float) -> float:
    """Compression-to-tension steel area ratio Asc/Ast with legacy zero fallback."""
    Ast_f = float(Ast or 0.0)
    Asc_f = float(Asc or 0.0)
    return (Asc_f / Ast_f) if Ast_f > 0 else 0.0


def deflection_sustained_load_factor(Asc: float, Ast: float) -> float:
    """AS 3600 long-term deflection sustained-load multiplier kcs."""
    ratio_Asc_Ast = compression_to_tension_steel_ratio(Asc, Ast)
    return max(2.0 - 1.2 * ratio_Asc_Ast, 0.8)


def effective_stiffness_coefficient_k1(Ief: float, beff: float, d: float) -> float:
    """Dimensionless effective-stiffness coefficient k1 = Ief / (beff d^3)."""
    try:
        Ief_f = float(Ief or 0.0)
        beff_f = float(beff or 0.0)
        d_f = float(d or 0.0)
    except Exception:
        return 0.0
    denom = beff_f * (d_f**3)
    return (Ief_f / denom) if denom > 0.0 else 0.0


def span_to_depth_ratio(L_mm: float, d_mm: float) -> float:
    """Span/depth ratio with the legacy zero fallback for non-positive depth."""
    L_f = float(L_mm)
    d_f = float(d_mm)
    return (L_f / d_f) if d_f > 0.0 else 0.0


def calc_deflection_as3600(
    L_m,
    Ec,
    Ief,
    g_kNm,
    q_kNm,
    psi_s,
    support_type,
    Ast,
    Asc,
):
    """Return short-term, long-term, and total deflection components in mm."""
    if L_m is None:
        return {
            "ok": False,
            "error": "Effective span is missing (L_m is None).",
        }
    try:
        L_m = float(L_m)
    except Exception:
        return {"ok": False, "error": "Effective span is not a valid number."}
    if L_m <= 0:
        return {"ok": False, "error": "Effective span must be > 0."}
    L_mm = L_m * 1000.0
    L4 = L_mm**4
    Ief = max(Ief, 1.0)
    Ec = max(Ec, 1.0)

    k2 = support_props(support_type).get("k2", 5.0 / 384.0)

    # 1 kN/m is numerically 1 N/mm.
    w_total = g_kNm + q_kNm
    w_sust = g_kNm + psi_s * q_kNm

    delta_short_total = k2 * w_total * L4 / (Ec * Ief)
    delta_short_sust = k2 * w_sust * L4 / (Ec * Ief)

    kcs = deflection_sustained_load_factor(Asc, Ast)

    delta_long_add = kcs * delta_short_sust
    delta_total = delta_short_total + delta_long_add

    return dict(
        L_mm=L_mm,
        k2=k2,
        w_total=w_total,
        w_sust=w_sust,
        delta_short_total=delta_short_total,
        delta_short_sust=delta_short_sust,
        kcs=kcs,
        delta_long_add=delta_long_add,
        delta_total=delta_total,
    )


def calc_span_depth_limit(
    ief,
    beff,
    bw,
    d,
    fc,
    Ec,
    Fdef_kNm,
    support_type,
    defl_limit_ratio,
):
    """
    Deemed-to-conform span/depth ratio from AS 3600:2018 Cl. 8.5.4.
    Returns (L_over_d_limit, k1, k2).
    """
    beff = max(beff if beff is not None else 1.0, 1.0)
    bw = max(bw if bw is not None else 1.0, 1.0)
    d = max(d if d is not None else 1.0, 1.0)
    Ec = max(Ec if Ec is not None else 1.0, 1.0)
    ief = max(ief if ief is not None else 1.0, 1.0)
    fc = fc if fc is not None else 32.0
    Fdef_kNm = Fdef_kNm if Fdef_kNm is not None else 0.0
    defl_limit_ratio = defl_limit_ratio if defl_limit_ratio is not None else 250.0

    k1 = effective_stiffness_coefficient_k1(ief, beff, d)
    k2 = support_props(support_type).get("k2", 5.0 / 384.0)

    delta_over_L = 1.0 / defl_limit_ratio if defl_limit_ratio > 0 else 0.0
    Fdef = Fdef_kNm

    if Fdef <= 0 or delta_over_L <= 0:
        return None, k1, k2

    inside = (k1 * delta_over_L * beff * Ec) / (k2 * Fdef)
    if inside <= 0:
        return None, k1, k2

    L_over_d_limit = inside ** (1.0 / 3.0)
    return L_over_d_limit, k1, k2


def span_depth_display_values(L_over_d, L_over_d_limit):
    """Display/status values for the deemed-to-conform span/depth check."""
    L_over_d_value = float(L_over_d) if L_over_d is not None else None
    limit_value = float(L_over_d_limit) if L_over_d_limit is not None else None

    util_span = (
        L_over_d_value / limit_value
        if limit_value is not None
        and limit_value > 0
        and L_over_d_value is not None
        else None
    )
    span_passes = (
        L_over_d_value <= limit_value
        if limit_value is not None
        and limit_value > 0
        and L_over_d_value is not None
        and L_over_d_value > 0
        else None
    )
    span_defl_status = (
        "pass" if span_passes is True else "fail" if span_passes is False else None
    )
    result_text = (
        "PASS"
        if span_defl_status == "pass"
        else "FAIL"
        if span_defl_status == "fail"
        else "—"
    )
    limit_text = f"{limit_value:.1f}" if limit_value is not None else "—"

    return {
        "util_span": util_span,
        "span_passes": span_passes,
        "span_defl_status": span_defl_status,
        "result_text": result_text,
        "limit_text": limit_text,
    }


def deflection_limit_check_values(delta_mm, L_mm, defl_limit_ratio):
    """Limit, utilisation, and pass/fail display values for deflection checks."""
    ratio = float(defl_limit_ratio or 0.0)
    span_mm = float(L_mm or 0.0)
    delta = float(delta_mm or 0.0)

    limit_delta_mm = span_mm / ratio if ratio > 0.0 else None
    utilisation = (
        delta / limit_delta_mm
        if limit_delta_mm is not None and limit_delta_mm > 0.0
        else None
    )
    status = (
        "pass"
        if utilisation is not None and utilisation <= 1.0
        else "fail"
        if utilisation is not None
        else None
    )
    result_text = (
        "PASS"
        if status == "pass"
        else "FAIL"
        if status == "fail"
        else "—"
    )

    return {
        "limit_delta_mm": limit_delta_mm,
        "utilisation": utilisation,
        "status": status,
        "result_text": result_text,
        "limit_delta_mm_display": limit_delta_mm if limit_delta_mm is not None else 0.0,
        "utilisation_display": utilisation if utilisation is not None else 0.0,
    }
