# shear_diagrams.py
# ==========================================
# Shear diagram generation functions
# ==========================================

import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch, Circle
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import strain_display
from bending_layer_semantics import resolve_bending_layer_geometry
from section_layout import compute_shear_reo_layout_pure
from section_props.plotly_section import make_sectionA_figure
from section_props.plot import plot_shape, apply_section_axes
from ui.diagrams.shear_diagram import (
    plot_shear_step3_section_params_plotly as _shared_plot_shear_step3_section_params_plotly,
    plot_shear_torsion_section_2d as _shared_plot_shear_torsion_section_2d,
)
from ui.diagrams.mcft_diagram import (
    make_mcft_longitudinal_strain_profile_fig as _shared_make_mcft_longitudinal_strain_profile_fig,
    make_step4_longitudinal_strain_diagram as _shared_make_step4_longitudinal_strain_diagram,
    plot_shear_step4_middepth_strain_diagram as _shared_plot_shear_step4_middepth_strain_diagram,
    plot_step4_mcft_strain_diagram as _shared_plot_step4_mcft_strain_diagram,
)
from ui.diagrams.check6_support_transfer_diagram import (
    build_shear_check6_support_transfer_diagram as _shared_build_shear_check6_support_transfer_diagram,
)
from ui.diagrams.torsion_diagram import (
    build_torsion_plotly_figure as _shared_build_torsion_plotly_figure,
    clamp_inside as _shared_clamp_inside,
    draw_face_label_debug as _shared_draw_face_label_debug,
    plot_shear_step1_theta_cracks_3d as _shared_plot_shear_step1_theta_cracks_3d,
    proj as _shared_proj,
    ray_rect_hit_2d as _shared_ray_rect_hit_2d,
    surface_point as _shared_surface_point,
)


def _arrow(ax, p0, p1, lw=2.0, ms=14, color="k"):
    ax.add_patch(
        FancyArrowPatch(
            p0, p1,
            arrowstyle="-|>",
            mutation_scale=ms,
            linewidth=lw,
            color=color,
        )
    )


def plot_shear_torsion_section_2d(
    *,
    shape_name: str,
    dims: dict,
    reo: dict,
    mode: str = "V+T",  # "V", "T", "V+T"
    show_labels: bool = True,
    tension_face: str | None = None,
    compact_stress_labels: bool = False,
    show_schematic_footer: bool = True,
):
    return _shared_plot_shear_torsion_section_2d(
        shape_name=shape_name,
        dims=dims,
        reo=reo,
        mode=mode,
        show_labels=show_labels,
        tension_face=tension_face,
        compact_stress_labels=compact_stress_labels,
        show_schematic_footer=show_schematic_footer,
    )


# ------------------------------------------------------------
#  Plotly Section Diagrams
# ------------------------------------------------------------

def plot_shear_step3_section_params_plotly(
    b_mm: float,
    D_mm: float,
    bv_mm: float,
    dv_mm: float,
    Asv_mm2: float | None = None,
    s_lig_mm: float | None = None,
    reo_shapes: list[dict] | None = None,
    lig_d: float | None = None,
    lig_legs: int | None = None,
    cover_bot: float | None = None,
    cover_top: float | None = None,
    cover_side: float | None = None,
    height: int = 850,  # 2.5x bigger (340 * 2.5 = 850)
    label_pad: int = 14,
    # NEW (optional): shape-aware mode
    shape_name: str | None = None,
    dims: dict | None = None,
    reo: dict | None = None,
):
    return _shared_plot_shear_step3_section_params_plotly(
        b_mm=b_mm,
        D_mm=D_mm,
        bv_mm=bv_mm,
        dv_mm=dv_mm,
        Asv_mm2=Asv_mm2,
        s_lig_mm=s_lig_mm,
        reo_shapes=reo_shapes,
        lig_d=lig_d,
        lig_legs=lig_legs,
        cover_bot=cover_bot,
        cover_top=cover_top,
        cover_side=cover_side,
        height=height,
        label_pad=label_pad,
        shape_name=shape_name,
        dims=dims,
        reo=reo,
    )


# Check 4 longitudinal diagram: fixed symmetric x-range so the internal beam face (x = 0) is
# identical in stress–strain and force-resolution modes (same scale, margins, extents).
def make_mcft_longitudinal_strain_profile_fig(
    eps_top_uls: float,
    eps_x_mcft: float,
    eps_bot_uls: float,
    title: str = "Longitudinal strain profile",
    height: int = 430,
    *,
    force_resolution: bool = False,
    force_section_D_mm: float | None = None,
    force_section_c_mm: float | None = None,
    force_section_gamma: float | None = None,
    force_tension_steel_y_from_top_mm: float | None = None,
    force_moment_sign: str = "positive",
    force_theta_deg: float | None = None,
):
    return _shared_make_mcft_longitudinal_strain_profile_fig(
        eps_top_uls=eps_top_uls,
        eps_x_mcft=eps_x_mcft,
        eps_bot_uls=eps_bot_uls,
        title=title,
        height=height,
        force_resolution=force_resolution,
        force_section_D_mm=force_section_D_mm,
        force_section_c_mm=force_section_c_mm,
        force_section_gamma=force_section_gamma,
        force_tension_steel_y_from_top_mm=force_tension_steel_y_from_top_mm,
        force_moment_sign=force_moment_sign,
        force_theta_deg=force_theta_deg,
    )


def plot_shear_step4_middepth_strain_diagram(
    b_mm: float,
    D_mm: float,
    eps_x: float,
    *,
    title: str = "Mid-depth longitudinal strain",
):
    return _shared_plot_shear_step4_middepth_strain_diagram(
        b_mm=b_mm,
        D_mm=D_mm,
        eps_x=eps_x,
        title=title,
    )


def plot_step4_mcft_strain_diagram(
    D_mm: float,
    eps_mid: float,
    eps_top: float,
    eps_bot: float,
    *,
    title: str = "Longitudinal strain profile",
):
    return _shared_plot_step4_mcft_strain_diagram(
        D_mm=D_mm,
        eps_mid=eps_mid,
        eps_top=eps_top,
        eps_bot=eps_bot,
        title=title,
    )


def make_step4_longitudinal_strain_diagram(
    D_mm: float,
    eps_x: float,
    eps_top: float,
    eps_bot: float,
    eps_min: float = -2.0e-4,
    eps_max: float = 3.0e-3,
    height_px: int = 540,
):
    return _shared_make_step4_longitudinal_strain_diagram(
        D_mm=D_mm,
        eps_x=eps_x,
        eps_top=eps_top,
        eps_bot=eps_bot,
        eps_min=eps_min,
        eps_max=eps_max,
        height_px=height_px,
    )


# ------------------------------------------------------------
#  3D Torsion/Shear Crack Helix Diagram (Unwrapped Surface)
# ------------------------------------------------------------

def proj(P, a=-0.65, b=0.28):
    return _shared_proj(P, a=a, b=b)


def clamp_inside(val, lo, hi, eps=1e-6):
    return _shared_clamp_inside(val, lo, hi, eps=eps)


def ray_rect_hit_2d(p, d, umin, umax, vmin, vmax, eps=1e-9):
    return _shared_ray_rect_hit_2d(p, d, umin, umax, vmin, vmax, eps=eps)


def surface_point(x, s, B, D):
    return _shared_surface_point(x, s, B, D)


def draw_face_label_debug(
    cam_a=-0.65,
    cam_b=0.28,
    L=10.0,
    B=3.2,
    D=2.4,
    fs=10,
    show_corners=True,
    n_cracks=3,
    start_t_min=0.1,
    start_t_span=0.3,
    crack_lw=4.0,
    show_cracks=False,
    k_slope=0.5,
    s0_min=0.1,
    theta_deg=45.0,
):
    return _shared_draw_face_label_debug(
        cam_a=cam_a,
        cam_b=cam_b,
        L=L,
        B=B,
        D=D,
        fs=fs,
        show_corners=show_corners,
        n_cracks=n_cracks,
        start_t_min=start_t_min,
        start_t_span=start_t_span,
        crack_lw=crack_lw,
        show_cracks=show_cracks,
        k_slope=k_slope,
        s0_min=s0_min,
        theta_deg=theta_deg,
    )


def plot_shear_step1_theta_cracks_3d(
    L_mm: float,
    b_mm: float,
    D_mm: float,
    theta_deg: float = 45.0,
    cam_a: float = -0.65,
    cam_b: float = 0.28,
    n_cracks: int = 3,
    start_t_min: float = 0.10,
    start_t_span: float = 0.06,
    crack_lw: float = 4.0,
    show_cracks: bool = True,
):
    return _shared_plot_shear_step1_theta_cracks_3d(
        L_mm=L_mm,
        b_mm=b_mm,
        D_mm=D_mm,
        theta_deg=theta_deg,
        cam_a=cam_a,
        cam_b=cam_b,
        n_cracks=n_cracks,
        start_t_min=start_t_min,
        start_t_span=start_t_span,
        crack_lw=crack_lw,
        show_cracks=show_cracks,
    )


def infer_shear_check6_critical_support_side(state: dict) -> str:
    """
    Heuristic governing support for the local Check 6 transfer sketch (left | right).
    Uses resolved deflection/support type, design section position, or eccentric point-load reactions.
    """
    try:
        from deflection import get_resolved_deflection_support_type

        stype = str(get_resolved_deflection_support_type(state) or "").strip()
    except Exception:
        stype = ""
    if stype == "Cantilever":
        return "left"

    try:
        from state_and_helpers import get_param

        L_mm = float(state.get("L") or get_param("L", 3000.0))
    except Exception:
        L_mm = 3000.0
    span_m = max(L_mm / 1000.0, 1e-6)

    design_source = str(
        state.get("design_actions_source") or state.get("actions_source") or "max"
    ).strip().lower()
    if design_source == "section":
        try:
            x_m = float(state.get("design_section_x_m", 0.0) or 0.0)
        except Exception:
            x_m = 0.0
        return "left" if x_m < 0.5 * span_m else "right"

    case = str(state.get("sfd_case") or state.get("load_case") or "").lower()
    if "from left" in case and "point" in case:
        try:
            from state_and_helpers import get_param

            a_m = float(
                state.get("a_m")
                or state.get("load_a_point")
                or state.get("sfd_a_udl")
                or get_param("a_m", span_m * 0.5)
            )
        except Exception:
            a_m = span_m * 0.5
        a_m = max(0.0, min(a_m, span_m))
        r_left = 1.0 - a_m / span_m
        r_right = a_m / span_m
        return "left" if r_left >= r_right else "right"

    return "left"


def _check6_float(state: dict, key: str, default: float) -> float:
    try:
        v = state.get(key, default)
        if v is None:
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _check6_clamp_mm(x: float, lo: float, hi: float) -> float:
    return max(lo, min(float(x), hi))


def _check6_build_sfd_params_uls(state: dict) -> tuple[str, float, dict] | None:
    """Rebuild ULS-equivalent params for ``_compute_diagram_arrays`` from shared/session keys."""
    try:
        from state_and_helpers import get_param
    except Exception:
        return None

    mode = str(state.get("sfd_beam_system_mode") or get_param("sfd_beam_system_mode", "Single span"))
    L_m = state.get("sfd_L_m")
    try:
        L_m = float(L_m) if L_m is not None else float(get_param("L", 3000.0)) / 1000.0
    except Exception:
        L_m = float(get_param("L", 3000.0)) / 1000.0
    L_m = max(L_m, 0.1)

    gamma_g = 1.2
    gamma_q = 1.5

    if mode.strip().lower() == "multi-span":
        try:
            n_spans = int(float(state.get("sfd_span_count") or get_param("sfd_span_count", 2) or 2))
        except Exception:
            n_spans = 2
        n_spans = max(2, min(n_spans, 5))
        nodes: list[float] = [0.0]
        for i in range(1, n_spans + 1):
            Li = state.get(f"sfd_span_len_{i}")
            if Li is None:
                Li = get_param(f"sfd_span_len_{i}", None)
            if Li is None:
                Li = max(0.2, L_m / max(n_spans, 1))
            nodes.append(nodes[-1] + max(0.2, float(Li)))
        L_tot = float(nodes[-1])
        types: list[str] = []
        for j in range(1, n_spans + 2):
            tj = state.get(f"sfd_support_type_{j}") or get_param(f"sfd_support_type_{j}", "Pinned")
            types.append(str(tj))

        psi_p = _check6_float(state, "load_psi_point", float(get_param("psi_point", 0.4)))
        n_point = int(_check6_float(state, "sfd_ms_point_count", 2.0))
        point_loads: list[dict] = []
        for i in range(1, max(0, n_point) + 1):
            G = _check6_float(state, f"load_ms_G_{i}", 30.0)
            Q = _check6_float(state, f"load_ms_Q_{i}", 20.0)
            x_i = _check6_clamp_mm(
                _check6_float(state, f"load_ms_x_{i}", L_tot * 0.25 * i),
                0.0,
                L_tot,
            )
            point_loads.append(
                {"x_m": x_i, "P_kN": max(1e-6, gamma_g * G + gamma_q * Q)}
            )

        n_udl = int(_check6_float(state, "sfd_ms_udl_count", 1.0))
        udl_loads: list[dict] = []
        for i in range(1, max(0, n_udl) + 1):
            g_i = _check6_float(state, f"load_ms_g_{i}", 5.0)
            q_i = _check6_float(state, f"load_ms_q_{i}", 3.0)
            x0 = _check6_float(state, f"load_ms_x0_{i}", 0.0)
            x1 = _check6_float(state, f"load_ms_x1_{i}", L_tot)
            xa, xb = (min(x0, x1), max(x0, x1))
            xa = _check6_clamp_mm(xa, 0.0, L_tot)
            xb = _check6_clamp_mm(xb, 0.0, L_tot)
            if xb > xa + 1e-9:
                udl_loads.append(
                    {
                        "x_start_m": xa,
                        "x_end_m": xb,
                        "w_kN_per_m": max(0.0, gamma_g * g_i + gamma_q * q_i),
                    }
                )

        params = {
            "beam_system_mode": "Multi-span",
            "node_positions_m": nodes,
            "support_types": types,
            "point_loads": point_loads,
            "udl_loads": udl_loads,
        }
        return "Multi-span continuous beam", L_tot, params

    case = str(
        state.get("load_case")
        or state.get("sfd_case")
        or get_param("sfd_case", "Simple beam – UDL over entire span")
    ).strip()
    if "Multi-span" not in case:
        case = case.replace("-", "–")
    sc = str(
        state.get("sfd_support_condition")
        or get_param("sfd_support_condition", "Simply supported")
    ).replace("-", "–")
    params: dict[str, object] = {"support_condition": sc, "beam_system_mode": "Single span"}

    if case in (
        "Simple beam – UDL over entire span",
        "Simple beam – partial UDL from left (length a)",
        "Cantilever – UDL over entire span",
    ):
        wu = state.get("w_uls_kNm_per_m")
        try:
            wu = float(wu) if wu is not None else None
        except Exception:
            wu = None
        if wu is None or wu <= 0:
            g = float(get_param("g_udl_kNm_per_m", 0.0) or 0.0)
            q = float(get_param("q_udl_kNm_per_m", 0.0) or 0.0)
            wu = gamma_g * g + gamma_q * q
        params["w"] = max(float(wu), 1e-6)
        if case == "Simple beam – partial UDL from left (length a)":
            params["a_udl"] = _check6_clamp_mm(
                _check6_float(state, "sfd_a_udl", L_m * 0.5),
                0.0,
                L_m,
            )
    elif case == "Simple beam – point load at centre":
        params["P"] = max(
            1e-6,
            _check6_float(state, "P_uls_kN", float(get_param("P_uls_kN", 100.0) or 100.0)),
        )
    elif case == "Simple beam – point load at distance a from left":
        params["P"] = max(
            1e-6,
            _check6_float(state, "P_uls_kN", float(get_param("P_uls_kN", 100.0) or 100.0)),
        )
        params["a"] = _check6_clamp_mm(
            _check6_float(state, "load_a_point", _check6_float(state, "a_m", L_m / 3.0)),
            0.0,
            L_m,
        )
    elif case == "Cantilever – point load at free end":
        params["P"] = max(
            1e-6,
            _check6_float(state, "P_uls_kN", float(get_param("P_uls_kN", 80.0) or 80.0)),
        )
    elif case == "Cantilever – point load at distance a from fixed end":
        params["P"] = max(
            1e-6,
            _check6_float(state, "P_uls_kN", float(get_param("P_uls_kN", 80.0) or 80.0)),
        )
        params["a_cant"] = _check6_clamp_mm(
            _check6_float(state, "sfd_a_cant", float(get_param("a_cant_m", L_m * 0.5))),
            0.0,
            L_m,
        )
    elif case == "Overhanging beam – right overhang with point load at free end":
        L_main = _check6_float(state, "sfd_L_m", L_m)
        params["L_main"] = max(0.1, L_main)
        params["a_overhang"] = max(
            0.0,
            _check6_float(state, "sfd_a_overhang", float(get_param("a_overhang_m", 2.0))),
        )
        params["P"] = max(
            1e-6,
            _check6_float(state, "P_uls_kN", float(get_param("P_uls_kN", 100.0) or 100.0)),
        )
    elif case in ("Simple beam – multiple point loads", "Cantilever – multiple point loads"):
        return None
    else:
        _g = float(get_param("g_udl_kNm_per_m", 0.0) or 0.0)
        _q = float(get_param("q_udl_kNm_per_m", 0.0) or 0.0)
        params.setdefault("w", max(1e-6, gamma_g * _g + gamma_q * _q))

    return case, L_m, params


def _check6_govern_from_sfd(
    state: dict, *, d_mm: float
) -> tuple[str, str, dict] | None:
    """
    Returns (critical_side, support_draw_kind, meta) using the same SFD backend as the beam diagrams,
    or None if analysis cannot be run.
    critical_side: "left" | "right" | "internal"
    """
    try:
        from sfd_bmd_page import _compute_diagram_arrays
    except Exception:
        return None

    built = _check6_build_sfd_params_uls(state)
    if not built:
        return None
    case, L_m, params = built
    try:
        x_arr, V_arr, _M_arr, blen, meta = _compute_diagram_arrays(case, L_m, params)
    except Exception:
        return None

    x = np.asarray(x_arr, dtype=float)
    V = np.asarray(V_arr, dtype=float)
    if x.size < 2 or not math.isfinite(blen) or blen <= 0:
        return None

    d_m = max(float(d_mm), 1.0) / 1000.0
    probe = max(0.05 * blen, min(2.0 * d_m, 0.22 * blen))

    sup_x = [float(s) for s in (meta.get("support_positions") or [0.0, blen])]
    sup_x = sorted({max(0.0, min(blen, sx)) for sx in sup_x})

    if len(sup_x) <= 1 or case.startswith("Cantilever"):
        kind = _check6_support_kind_at_index(
            str(params.get("support_condition", "")),
            sup_x,
            [],
            0,
        )
        return "left", kind, meta

    if str(params.get("beam_system_mode")) == "Multi-span" and len(sup_x) >= 3:
        best_i = 0
        best_v = -1.0
        for i, xs in enumerate(sup_x):
            lo = max(0.0, xs - probe)
            hi = min(blen, xs + probe)
            mask = (x >= lo) & (x <= hi)
            vv = float(np.max(np.abs(V[mask]))) if np.any(mask) else 0.0
            if vv > best_v + 1e-9:
                best_v = vv
                best_i = i
        types = [str(t) for t in (meta.get("support_types") or [])]
        kind = _check6_support_kind_at_index("", sup_x, types, best_i)
        if best_i == 0:
            side = "left"
        elif best_i == len(sup_x) - 1:
            side = "right"
        else:
            side = "internal"
        meta = {**meta, "_check6_critical_support_index": best_i, "_check6_support_x_m": sup_x[best_i]}
        return side, kind, meta

    left_mask = x <= probe + 1e-9
    right_mask = x >= blen - probe - 1e-9
    v_left = float(np.max(np.abs(V[left_mask]))) if np.any(left_mask) else 0.0
    v_right = float(np.max(np.abs(V[right_mask]))) if np.any(right_mask) else 0.0
    if v_right > v_left + 1e-6:
        idx = len(sup_x) - 1
    else:
        idx = 0
    types = [str(t) for t in (meta.get("support_types") or [])]
    kind = _check6_support_kind_at_index(
        str(params.get("support_condition", "")),
        sup_x,
        types,
        idx,
    )
    side = "right" if idx > 0 else "left"
    return side, kind, meta


def _check6_norm_support_token(raw: str) -> str:
    return str(raw or "").strip().lower()


def _check6_support_kind_at_index(
    support_condition: str,
    support_x: list[float],
    support_types: list[str],
    index: int,
) -> str:
    """Return draw kind: pinned | roller | fixed | internal."""
    if support_types and len(support_types) == len(support_x) and 0 <= index < len(support_types):
        t = _check6_norm_support_token(support_types[index])
        if t == "fixed":
            return "fixed"
        if t == "roller":
            return "roller"
        if t == "pinned":
            return "pinned"
        return "pinned"

    sc = str(support_condition or "").replace("-", "–")
    end_right = index > 0 and index == len(support_x) - 1
    end_left = index == 0

    if sc == "Fixed–Free":
        return "fixed" if end_left else "free"
    if sc == "Simply supported":
        if end_left:
            return "pinned"
        if end_right:
            return "roller"
    if sc == "Pinned–Pinned":
        return "pinned"
    if sc == "Fixed–Pinned":
        return "fixed" if end_left else "pinned"
    if sc == "Pinned–Fixed":
        return "pinned" if end_left else "fixed"
    if sc == "Fixed–Fixed":
        return "fixed"

    if len(support_x) >= 3 and 0 < index < len(support_x) - 1:
        return "internal"

    return "pinned" if end_left else "roller"


def _check6_support_kind_match_session_visual(state: dict, side: str) -> str:
    """
    Pinned / roller / fixed / free to match ``shear_visuals`` side-view / behaviour supports
    (canonical deflection + load case), not a loose SFD string mismatch.
    """
    sn = str(side or "left").strip().lower()
    if sn == "internal":
        return "internal"
    try:
        from shear_visuals import (
            _get_canonical_shear_visual_loading_state,
            _get_canonical_shear_visual_support_state,
        )

        canon = _get_canonical_shear_visual_support_state(
            _get_canonical_shear_visual_loading_state()
        )
    except Exception:
        canon = "simply_supported"
    if canon == "cantilever":
        return "fixed" if sn == "left" else "free"
    if canon == "pinned_pinned":
        return "pinned"
    if sn == "left":
        return "pinned"
    if sn == "right":
        return "roller"
    return "pinned"


def resolve_check6_support_transfer_context(state: dict, *, d_mm: float) -> dict:
    """
    Governing support for Check 6 sketch: side, icon kind, optional SFD metadata.
    Draw kind matches session-wide shear visuals (simply supported → pinned left / roller right).
    """
    g = _check6_govern_from_sfd(state, d_mm=float(d_mm))
    if g:
        side, kind, meta = g
        if str(side) == "internal":
            kind = "internal"
        else:
            kind = _check6_support_kind_match_session_visual(state, side)
        return {
            "critical_support_side": side,
            "support_draw_kind": kind,
            "sfd_meta": meta,
        }
    side = infer_shear_check6_critical_support_side(state)
    kind = _check6_support_kind_match_session_visual(state, str(side))
    return {
        "critical_support_side": side,
        "support_draw_kind": kind,
        "sfd_meta": {},
    }


def build_shear_check6_support_transfer_diagram(
    *,
    layout: dict | None,
    D_mm: float,
    d_mm: float,
    moment_sign: str,
    support_draw_kind: str,
    critical_support_side: str,
    s_lig_mm: float,
    lig_legs: int,
    lig_d_mm: float = 10.0,
    asv_mm2: float | None = None,
    height: int = 320,
    fc_mpa: float | None = None,
    fsy_mpa: float | None = None,
    theta_v_deg: float | None = None,
    d_v_mm: float | None = None,
    show_mean_crack_guideline: bool = True,
    show_mean_green_flow_pulse: bool = True,
    show_mean_green_flow_arrows: bool = True,
    show_green_strut_flow: bool = False,
    show_compression_resultant: bool = True,
    show_shear_teaching_overlay: bool = False,
    show_region_labels: bool = True,
    show_mcft_mechanism_labels: bool = False,
    crack_bulge_scale: float = 1.28,
    crack_jag_scale: float = 0.88,
    web_crushing_stm: bool = False,
) -> go.Figure:
    return _shared_build_shear_check6_support_transfer_diagram(
        layout=layout,
        D_mm=D_mm,
        d_mm=d_mm,
        moment_sign=moment_sign,
        support_draw_kind=support_draw_kind,
        critical_support_side=critical_support_side,
        s_lig_mm=s_lig_mm,
        lig_legs=lig_legs,
        lig_d_mm=lig_d_mm,
        asv_mm2=asv_mm2,
        height=height,
        fc_mpa=fc_mpa,
        fsy_mpa=fsy_mpa,
        theta_v_deg=theta_v_deg,
        d_v_mm=d_v_mm,
        show_mean_crack_guideline=show_mean_crack_guideline,
        show_mean_green_flow_pulse=show_mean_green_flow_pulse,
        show_mean_green_flow_arrows=show_mean_green_flow_arrows,
        show_green_strut_flow=show_green_strut_flow,
        show_compression_resultant=show_compression_resultant,
        show_shear_teaching_overlay=show_shear_teaching_overlay,
        show_region_labels=show_region_labels,
        show_mcft_mechanism_labels=show_mcft_mechanism_labels,
        crack_bulge_scale=crack_bulge_scale,
        crack_jag_scale=crack_jag_scale,
        web_crushing_stm=web_crushing_stm,
    )


def build_torsion_plotly_figure(
    *,
    torsion_design_required: bool = True,
    L_mm: float | None = None,
    b_mm: float | None = None,
    D_mm: float | None = None,
    theta_crack_deg: float = 45.0,
    cam_a: float = -0.65,
    cam_b: float = 0.28,
) -> go.Figure:
    return _shared_build_torsion_plotly_figure(
        torsion_design_required=torsion_design_required,
        L_mm=L_mm,
        b_mm=b_mm,
        D_mm=D_mm,
        theta_crack_deg=theta_crack_deg,
        cam_a=cam_a,
        cam_b=cam_b,
    )

