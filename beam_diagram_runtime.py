"""Reusable beam-action analysis and SFD/BMD figure runtime.

The Design page composes these services; other engineering pages import this
module instead of importing the Design page.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache

import numpy as np

from beam_analysis import (
    build_beam_model_from_legacy_case,
    legacy_results_local_from_result,
    solve_beam_model,
    solve_beam_structure,
    solve_single_span_beam,
)
from calculations.deflection import defl_support_type_from_design_selection
from state_runtime_gateway import get_param, is_design_governing
from ui.diagrams.moment_shear_diagram import (
    figure_bmd_from_state,
    figure_sfd_from_state,
)


def _clamp_x(x_m: float, max_x: float) -> float:
    return max(0.0, min(float(x_m), float(max_x)))


def _defl_support_type_from_selection(
    load_case: str, support_condition: str | None
) -> str:
    return defl_support_type_from_design_selection(load_case, support_condition)


def _interp_at_x(x_vals, y_vals, x_m: float) -> float:
    if x_vals is None or y_vals is None or len(x_vals) == 0 or len(y_vals) == 0:
        return 0.0
    return float(np.interp(_clamp_x(x_m, float(x_vals[-1])), x_vals, y_vals))


def diagram_cache_fingerprint(
    case: str,
    L_uls: float,
    p_uls: dict,
    L_sls: float,
    p_sls: dict,
) -> str:
    """Return the stable beam case/load/support fingerprint."""

    def _pack(length: float, params: dict) -> dict:
        params = dict(params or {})
        keys = (
            "support_condition",
            "beam_system_mode",
            "node_positions_m",
            "support_types",
            "w",
            "P",
            "point_loads",
            "udl_loads",
            "L_main",
            "a_overhang",
            "a",
            "a_udl",
            "a_cant",
        )
        return {
            "L": round(float(length), 9),
            **{key: params.get(key) for key in keys},
        }

    blob = {
        "case": str(case),
        "uls": _pack(L_uls, p_uls),
        "sls": _pack(L_sls, p_sls),
    }
    return hashlib.sha256(
        json.dumps(blob, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:48]


def _compute_diagram_arrays_uncached(case_name: str, span_L: float, params: dict):
    """Solve the named beam case and return the legacy diagram tuple."""

    values = dict(params or {})
    length = float(span_L)
    if str(values.get("beam_system_mode", "Single span")) == "Multi-span":
        nodes = [float(v) for v in (values.get("node_positions_m") or [0.0, length])]
        supports = [
            str(v) for v in (values.get("support_types") or ["Pinned", "Pinned"])
        ]
        solved = solve_beam_structure(
            node_positions_m=nodes,
            support_types=supports,
            point_loads=list(values.get("point_loads") or []),
            udl_loads=list(values.get("udl_loads") or []),
            n_points_per_span=120,
        )
        x = np.asarray(solved["x"], dtype=float)
        shear = np.asarray(solved["V"], dtype=float)
        moment = np.asarray(solved["M"], dtype=float)
        beam_length = float(nodes[-1] - nodes[0]) if len(nodes) > 1 else length
        return x, shear, moment, beam_length, {
            "support_positions": list(solved.get("support_positions", nodes)),
            "support_types": supports,
            "reactions": dict(solved.get("reactions", {})),
            "analysis_note": "continuous multi-span beam solved via stiffness-based beam-analysis backend",
            "beam_system_mode": "Multi-span",
            "solver_metadata": dict(solved.get("metadata", {})),
        }

    support_condition = str(
        values.get("support_condition", "Simply supported")
    ).replace("-", "â€“")
    fixed_end_conditions = {"Fixedâ€“Pinned", "Pinnedâ€“Fixed", "Fixedâ€“Fixed"}
    is_overhang = (
        case_name == "Overhanging beam â€“ right overhang with point load at free end"
    )
    is_cantilever = case_name.startswith("Cantilever")

    if not is_overhang and support_condition in fixed_end_conditions:
        point_loads = list(values.get("point_loads") or [])
        if not point_loads and "P" in values:
            load = float(values.get("P", 0.0) or 0.0)
            if case_name == "Simple beam â€“ point load at centre":
                point_loads = [{"x_m": length / 2.0, "P_kN": load}]
            elif case_name == "Simple beam â€“ point load at distance a from left":
                point_loads = [
                    {
                        "x_m": _clamp_x(
                            float(values.get("a", length / 3.0) or length / 3.0),
                            length,
                        ),
                        "P_kN": load,
                    }
                ]
            elif case_name == "Cantilever â€“ point load at free end":
                point_loads = [{"x_m": length, "P_kN": load}]
            elif case_name == "Cantilever â€“ point load at distance a from fixed end":
                point_loads = [
                    {
                        "x_m": _clamp_x(
                            float(
                                values.get("a_cant", length / 2.0)
                                or length / 2.0
                            ),
                            length,
                        ),
                        "P_kN": load,
                    }
                ]

        udl_loads = list(values.get("udl_loads") or [])
        if not udl_loads and "w" in values:
            load = float(values.get("w", 0.0) or 0.0)
            if case_name in (
                "Simple beam â€“ UDL over entire span",
                "Cantilever â€“ UDL over entire span",
            ):
                udl_loads = [
                    {"x_start_m": 0.0, "x_end_m": length, "w_kN_per_m": load}
                ]
            elif case_name == "Simple beam â€“ partial UDL from left (length a)":
                udl_loads = [
                    {
                        "x_start_m": 0.0,
                        "x_end_m": _clamp_x(
                            float(
                                values.get("a_udl", length / 2.0)
                                or length / 2.0
                            ),
                            length,
                        ),
                        "w_kN_per_m": load,
                    }
                ]

        solved = solve_single_span_beam(
            L_m=length,
            support_condition=support_condition,
            point_loads=point_loads,
            udl_loads=udl_loads,
            n_points=400,
        )
        x = np.asarray(solved["x"], dtype=float)
        shear = np.asarray(solved["V"], dtype=float)
        moment = np.asarray(solved["M"], dtype=float)
        reactions = solved.get("reactions", {})
        return x, shear, moment, length, {
            "R1": float(reactions.get("R_left", 0.0)),
            "R2": float(reactions.get("R_right", 0.0)),
            "M_left": float(reactions.get("M_left", 0.0)),
            "M_right": float(reactions.get("M_right", 0.0)),
            "reactions": {
                "R1": float(reactions.get("R_left", 0.0)),
                "R2": float(reactions.get("R_right", 0.0)),
                "M1": float(reactions.get("M_left", 0.0)),
                "M2": float(reactions.get("M_right", 0.0)),
            },
            "support_positions": list(
                solved.get("support_positions", [0.0, length])
            ),
            "support_condition": support_condition,
            "analysis_note": "statically indeterminate solved via beam-analysis backend",
            "solver_metadata": dict(solved.get("metadata", {})),
        }

    if is_cantilever:
        values["support_condition"] = "Fixedâ€“Free"
    model = build_beam_model_from_legacy_case(case_name, length, values)
    result = solve_beam_model(model, n_points=400)
    x = np.asarray(result.x, dtype=float)
    shear = np.asarray(result.V, dtype=float)
    moment = np.asarray(result.M, dtype=float)
    beam_length = float(model.length_m)
    local = legacy_results_local_from_result(case_name, model, result)
    if is_overhang:
        local["support_positions"] = [0.0, float(values.get("L_main", length))]
    elif case_name.startswith("Cantilever"):
        local["support_positions"] = [0.0]
    else:
        local["support_positions"] = [0.0, beam_length]
    local["support_condition"] = str(
        values.get("support_condition", support_condition)
    )
    return x, shear, moment, beam_length, local


def _json_cache_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"Unsupported diagram cache value: {type(value).__name__}")


@lru_cache(maxsize=128)
def _compute_diagram_arrays_cached(
    case_name: str,
    span_L: float,
    params_json: str,
):
    return _compute_diagram_arrays_uncached(
        case_name,
        span_L,
        json.loads(params_json),
    )


def compute_diagram_arrays(case_name: str, span_L: float, params: dict):
    """Solve a beam case, reusing identical immutable solver inputs across reruns.

    Numeric arrays and the small caller-facing metadata containers are copied.
    Large solver diagnostic matrices remain shared and must be treated as
    read-only; production callers only inspect them for derivation text.
    """

    params_json = json.dumps(
        dict(params or {}),
        sort_keys=True,
        separators=(",", ":"),
        default=_json_cache_default,
    )
    x, shear, moment, beam_length, local = _compute_diagram_arrays_cached(
        str(case_name),
        float(span_L),
        params_json,
    )
    local_copy = dict(local)
    for key in ("support_positions", "support_types"):
        if isinstance(local_copy.get(key), list):
            local_copy[key] = list(local_copy[key])
    if isinstance(local_copy.get("reactions"), dict):
        local_copy["reactions"] = dict(local_copy["reactions"])
    return (
        np.array(x, dtype=float, copy=True),
        np.array(shear, dtype=float, copy=True),
        np.array(moment, dtype=float, copy=True),
        float(beam_length),
        local_copy,
    )


def diagram_solver_cache_clear() -> None:
    _compute_diagram_arrays_cached.cache_clear()


def diagram_solver_cache_info():
    return _compute_diagram_arrays_cached.cache_info()


_compute_diagram_arrays = compute_diagram_arrays


def _prepare_sfd_bmd_plot_state(
    x,
    V,
    M,
    case: str | None = None,
    L: float | None = None,
    support_positions: list[float] | None = None,
    support_types: list[str] | None = None,
    preview_x_m: float | None = None,
    design_x_m: float | None = None,
    preview_V: float | None = None,
    preview_M: float | None = None,
) -> dict:
    if L is None and x is not None and len(x) > 0:
        L = float(x[-1])
    positions = (
        [] if support_positions is None else [float(v) for v in support_positions]
    )
    if not positions and case and L is not None:
        if str(case).startswith("Simple beam"):
            positions = [0.0, float(L)]
        elif str(case).startswith("Cantilever"):
            positions = [0.0]
    length = float(L or 0.0)
    d_v_mm = float(get_param("d_v", 0.0) or 0.0)
    return {
        "L": L,
        "case": case,
        "x_plot": x.tolist() if hasattr(x, "tolist") else list(x or []),
        "V_plot": V.tolist() if hasattr(V, "tolist") else list(V or []),
        "M_plot": M.tolist() if hasattr(M, "tolist") else list(M or []),
        "support_positions_plot": positions,
        "support_types_plot": list(support_types or []),
        "preview_x_m": preview_x_m,
        "design_x_m": design_x_m,
        "preview_V": preview_V,
        "preview_M": preview_M,
        "x_pad": max(length * 0.08, 0.12),
        "support_type": str(
            get_param("support_type", "simply_supported") or "simply_supported"
        )
        .strip()
        .lower(),
        "design_mode_active": bool(is_design_governing()),
        "zone_limit_m": 1.5 * d_v_mm / 1000.0,
        "d_v_mm": d_v_mm,
        "critical_shear_x": get_param("critical_shear_x"),
        "critical_shear_V": get_param("critical_shear_V"),
        "shear_spacing_end_mm": get_param("shear_spacing_end_mm"),
        "shear_spacing_mid_mm": get_param("shear_spacing_mid_mm"),
    }


def plot_sfd_bmd_plotly(
    x,
    V,
    M,
    case: str | None = None,
    L: float | None = None,
    support_positions: list[float] | None = None,
    support_types: list[str] | None = None,
    preview_x_m: float | None = None,
    design_x_m: float | None = None,
    preview_V: float | None = None,
    preview_M: float | None = None,
    *,
    show_m_peak: bool = False,
):
    state = _prepare_sfd_bmd_plot_state(
        x,
        V,
        M,
        case=case,
        L=L,
        support_positions=support_positions,
        support_types=support_types,
        preview_x_m=preview_x_m,
        design_x_m=design_x_m,
        preview_V=preview_V,
        preview_M=preview_M,
    )
    return figure_sfd_from_state(state), figure_bmd_from_state(
        state, show_m_peak=show_m_peak
    )


__all__ = [
    "_clamp_x",
    "_compute_diagram_arrays",
    "_defl_support_type_from_selection",
    "_prepare_sfd_bmd_plot_state",
    "compute_diagram_arrays",
    "diagram_cache_fingerprint",
    "diagram_solver_cache_clear",
    "diagram_solver_cache_info",
    "plot_sfd_bmd_plotly",
]
