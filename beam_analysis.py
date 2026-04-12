"""
Determinate single-span beam analysis core (Phase 1).

Provides a beam model, legacy-case adapter, and solver for simply supported,
cantilever (fixed–free), and two-support overhang geometries.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

SupportType = Literal["fixed", "pinned", "roller", "free"]
LoadType = Literal["point", "udl"]


@dataclass
class Support:
    x_m: float
    kind: SupportType


@dataclass
class PointLoad:
    x_m: float
    P_kN: float  # downward positive


@dataclass
class UDLLoad:
    x_start_m: float
    x_end_m: float
    w_kN_per_m: float  # downward positive


@dataclass
class BeamModel:
    length_m: float
    supports: list[Support] = field(default_factory=list)
    point_loads: list[PointLoad] = field(default_factory=list)
    udl_loads: list[UDLLoad] = field(default_factory=list)


@dataclass
class BeamAnalysisResult:
    x: list[float]
    V: list[float]
    M: list[float]
    reactions: dict[str, float]
    support_positions: list[float]
    metadata: dict


def _clamp_segment_to_beam(s: float, e: float, L: float) -> tuple[float, float] | None:
    s = max(0.0, float(s))
    e = min(float(L), float(e))
    if e <= s:
        return None
    return s, e


def _total_downward_load(model: BeamModel, L: float) -> float:
    total = 0.0
    for pl in model.point_loads:
        if 0.0 <= pl.x_m <= L:
            total += pl.P_kN
    for udl in model.udl_loads:
        seg = _clamp_segment_to_beam(udl.x_start_m, udl.x_end_m, L)
        if seg:
            total += udl.w_kN_per_m * (seg[1] - seg[0])
    return total


def _moment_of_loads_about(model: BeamModel, L: float, pivot_x: float) -> float:
    """Moment of all downward loads about pivot_x (sagging / CCW on +x beam = positive)."""
    m = 0.0
    for pl in model.point_loads:
        if 0.0 <= pl.x_m <= L:
            m += pl.P_kN * (pl.x_m - pivot_x)
    for udl in model.udl_loads:
        seg = _clamp_segment_to_beam(udl.x_start_m, udl.x_end_m, L)
        if not seg:
            continue
        s, e = seg
        length = e - s
        force = udl.w_kN_per_m * length
        centroid = s + 0.5 * length
        m += force * (centroid - pivot_x)
    return m


def _vertical_reactions_two_supports(model: BeamModel, L: float, x0: float, x1: float) -> tuple[float, float]:
    """Pinned/roller line: R at x0 and x1, upward positive."""
    span = x1 - x0
    if abs(span) < 1e-12:
        raise ValueError("Two supports coincide")
    m_about_x0 = _moment_of_loads_about(model, L, x0)
    r1 = m_about_x0 / span
    r0 = _total_downward_load(model, L) - r1
    return r0, r1


def _shear_moment_two_support(
    x: float,
    L: float,
    x0: float,
    x1: float,
    r0: float,
    r1: float,
    model: BeamModel,
) -> tuple[float, float]:
    """
    Sign convention (matches legacy SFD page):
    Left support reaction is included for x >= x0 (inclusive at the left end).
    Interior/right support reaction is included only for x strictly past that support
    (so a support at the beam end x=L does not enter V on the sampled [0, L] grid).
    Downward loads at or left of the cut are subtracted from V; matching moments about x.
    """
    tol = 1e-9
    v = 0.0
    m = 0.0

    if x >= x0 - tol:
        v += r0
        m += r0 * (x - x0)
    if x > x1 + tol:
        v += r1
        m += r1 * (x - x1)

    for pl in model.point_loads:
        if not (0.0 <= pl.x_m <= L):
            continue
        if pl.x_m <= x + tol:
            # Legacy SFD page: point load at the free tip (x = L) is not subtracted at the
            # last station, so V there stays RA+RB rather than dropping to zero.
            if abs(pl.x_m - L) < tol and abs(x - L) < tol:
                pass
            else:
                v -= pl.P_kN
            m -= pl.P_kN * (x - pl.x_m)

    for udl in model.udl_loads:
        seg = _clamp_segment_to_beam(udl.x_start_m, udl.x_end_m, L)
        if not seg:
            continue
        s_raw, e_raw = seg
        e_use = min(e_raw, x)
        if e_use <= s_raw:
            continue
        length = e_use - s_raw
        force = udl.w_kN_per_m * length
        centroid = s_raw + 0.5 * length
        v -= force
        m -= force * (x - centroid)

    return v, m


def _shear_moment_cantilever(
    x: float,
    L: float,
    model: BeamModel,
) -> tuple[float, float]:
    """
    Fixed at left, free at right. Legacy convention:
    V = minus resultant downward load on the segment to the right of the cut (including
        a point load located exactly at the cut station).
    M = minus moment of that same right-side loading about the cut.
    """
    tol = 1e-9
    f_down = 0.0
    mom = 0.0

    for pl in model.point_loads:
        if 0.0 <= pl.x_m <= L and pl.x_m >= x - tol:
            f_down += pl.P_kN
            mom += pl.P_kN * (pl.x_m - x)

    for udl in model.udl_loads:
        seg = _clamp_segment_to_beam(udl.x_start_m, udl.x_end_m, L)
        if not seg:
            continue
        s_raw, e_raw = seg
        s_use = max(s_raw, x)
        if e_raw <= s_use + tol:
            continue
        length = e_raw - s_use
        force = udl.w_kN_per_m * length
        centroid = s_use + 0.5 * length
        f_down += force
        mom += force * (centroid - x)

    v = -f_down
    m = -mom
    return v, m


def _classify_determinate(model: BeamModel) -> str:
    sups = sorted(model.supports, key=lambda s: s.x_m)
    fixed_left = (
        len(sups) == 1
        and sups[0].kind == "fixed"
        and abs(sups[0].x_m) < 1e-9
    )
    if fixed_left:
        return "cantilever"
    vert_kinds = ("pinned", "roller")
    vert = [s for s in sups if s.kind in vert_kinds]
    if len(vert) == 2:
        return "two_support"
    raise NotImplementedError(
        f"Phase 1 solver: unsupported support layout ({[(s.x_m, s.kind) for s in sups]})"
    )


def solve_beam_model(model: BeamModel, n_points: int = 400) -> BeamAnalysisResult:
    """
    Solve determinate beam: two vertical supports (simple or overhang) or single fixed left cantilever.
    Multiple point loads and multiple UDL segments are supported.
    """
    L = float(model.length_m)
    if L <= 0.0 or not math.isfinite(L):
        raise ValueError("Beam length must be positive and finite")

    mode = _classify_determinate(model)
    sups = sorted(model.supports, key=lambda s: s.x_m)
    reactions: dict[str, float] = {}
    support_positions: list[float] = []
    metadata: dict = {"mode": mode, "length_m": L}

    r0 = r1 = 0.0
    x0 = x1 = 0.0

    if mode == "cantilever":
        support_positions = [0.0]
        r_fixed = _total_downward_load(model, L)
        m_fixed = _moment_of_loads_about(model, L, 0.0)
        reactions["R@0"] = r_fixed
        reactions["M@0"] = m_fixed
        metadata["fixed_shear_kN"] = r_fixed
        metadata["fixed_moment_kNm"] = m_fixed
    else:
        s0, s1 = sups[0], sups[1]
        x0, x1 = float(s0.x_m), float(s1.x_m)
        support_positions = [x0, x1]
        r0, r1 = _vertical_reactions_two_supports(model, L, x0, x1)
        reactions[f"R@{x0:g}"] = r0
        reactions[f"R@{x1:g}"] = r1
        metadata["support_x_m"] = [x0, x1]
        metadata["R_left"] = r0
        metadata["R_right"] = r1

    x_arr = np.linspace(0.0, L, int(n_points), dtype=float)
    v_arr = np.zeros_like(x_arr)
    m_arr = np.zeros_like(x_arr)

    for i, xv in enumerate(x_arr):
        if mode == "cantilever":
            v_arr[i], m_arr[i] = _shear_moment_cantilever(float(xv), L, model)
        else:
            v_arr[i], m_arr[i] = _shear_moment_two_support(float(xv), L, x0, x1, r0, r1, model)

    return BeamAnalysisResult(
        x=x_arr.tolist(),
        V=v_arr.tolist(),
        M=m_arr.tolist(),
        reactions=reactions,
        support_positions=support_positions,
        metadata=metadata,
    )


def _two_span_vertical_supports(L_m: float, support_condition: str | None) -> list[Support]:
    """Single-span simple cases: pin+roller (simply supported) vs pin+pin (pinned–pinned)."""
    Lm = float(L_m)
    sc = str(support_condition or "").strip().replace("-", "–")
    if sc == "Simply supported":
        return [Support(0.0, "pinned"), Support(Lm, "roller")]
    return [Support(0.0, "pinned"), Support(Lm, "pinned")]


def build_beam_model_from_legacy_case(case_name: str, L: float, params: dict) -> BeamModel:
    """Map existing SFD/BMD page cases to BeamModel."""
    p = params or {}
    L_local = float(L)
    point_load_rows = p.get("point_loads")

    _ss = _two_span_vertical_supports(L_local, p.get("support_condition"))

    if case_name == "Simple beam – UDL over entire span":
        w = float(p.get("w", 0.0) or 0.0)
        return BeamModel(
            length_m=L_local,
            supports=list(_ss),
            udl_loads=[UDLLoad(0.0, L_local, w)],
        )

    if case_name == "Simple beam – partial UDL from left (length a)":
        w = float(p.get("w", 0.0) or 0.0)
        a_udl = max(0.0, min(float(p.get("a_udl", L_local / 2.0)), L_local))
        return BeamModel(
            length_m=L_local,
            supports=list(_ss),
            udl_loads=[UDLLoad(0.0, a_udl, w)],
        )

    if case_name == "Simple beam – point load at centre":
        P = float(p.get("P", 0.0) or 0.0)
        return BeamModel(
            length_m=L_local,
            supports=list(_ss),
            point_loads=[PointLoad(L_local / 2.0, P)],
        )

    if case_name == "Simple beam – point load at distance a from left":
        P = float(p.get("P", 0.0) or 0.0)
        a_val = p.get("a", L_local / 3.0)
        a_val = max(0.0, min(float(a_val), L_local))
        return BeamModel(
            length_m=L_local,
            supports=list(_ss),
            point_loads=[PointLoad(a_val, P)],
        )

    if case_name == "Simple beam – multiple point loads":
        point_loads: list[PointLoad] = []
        for row in point_load_rows or []:
            try:
                x_m = max(0.0, min(float(row.get("x_m", 0.0)), L_local))
                p_kn = float(row.get("P_kN", 0.0) or 0.0)
            except (TypeError, ValueError, AttributeError):
                continue
            point_loads.append(PointLoad(x_m, p_kn))
        return BeamModel(
            length_m=L_local,
            supports=list(_ss),
            point_loads=point_loads,
        )

    if case_name == "Cantilever – point load at free end":
        P = float(p.get("P", 0.0) or 0.0)
        return BeamModel(
            length_m=L_local,
            supports=[Support(0.0, "fixed")],
            point_loads=[PointLoad(L_local, P)],
        )

    if case_name == "Cantilever – point load at distance a from fixed end":
        P = float(p.get("P", 0.0) or 0.0)
        a_cant = max(0.0, min(float(p.get("a_cant", L_local / 2.0)), L_local))
        return BeamModel(
            length_m=L_local,
            supports=[Support(0.0, "fixed")],
            point_loads=[PointLoad(a_cant, P)],
        )

    if case_name == "Cantilever – multiple point loads":
        point_loads: list[PointLoad] = []
        for row in point_load_rows or []:
            try:
                x_m = max(0.0, min(float(row.get("x_m", 0.0)), L_local))
                p_kn = float(row.get("P_kN", 0.0) or 0.0)
            except (TypeError, ValueError, AttributeError):
                continue
            point_loads.append(PointLoad(x_m, p_kn))
        return BeamModel(
            length_m=L_local,
            supports=[Support(0.0, "fixed")],
            point_loads=point_loads,
        )

    if case_name == "Cantilever – UDL over entire span":
        w = float(p.get("w", 0.0) or 0.0)
        return BeamModel(
            length_m=L_local,
            supports=[Support(0.0, "fixed")],
            udl_loads=[UDLLoad(0.0, L_local, w)],
        )

    if case_name == "Overhanging beam – right overhang with point load at free end":
        P = float(p.get("P", 0.0) or 0.0)
        L_main = float(p.get("L_main", L_local))
        a_over = float(p.get("a_overhang", 0.0))
        beam_len = L_main + a_over
        return BeamModel(
            length_m=beam_len,
            supports=[
                Support(0.0, "pinned"),
                Support(L_main, "pinned"),
            ],
            point_loads=[PointLoad(beam_len, P)],
        )

    raise ValueError(f"Unknown legacy load case: {case_name!r}")


def legacy_results_local_from_result(case_name: str, model: BeamModel, result: BeamAnalysisResult) -> dict:
    """Populate results_local keys expected by existing derivation / summary code."""
    out: dict = {}
    md = result.metadata
    if md.get("mode") == "cantilever":
        out["V_fixed"] = float(md.get("fixed_shear_kN", 0.0))
        out["M_fixed"] = float(md.get("fixed_moment_kNm", 0.0))
        return out
    if md.get("mode") != "two_support":
        return out

    x0, x1 = md["support_x_m"]
    r0 = float(result.reactions[f"R@{x0:g}"])
    r1 = float(result.reactions[f"R@{x1:g}"])

    if case_name == "Simple beam – UDL over entire span":
        out["R"] = r0
    elif case_name in (
        "Simple beam – partial UDL from left (length a)",
        "Simple beam – point load at centre",
        "Simple beam – point load at distance a from left",
        "Simple beam – multiple point loads",
    ):
        out["R1"] = r0
        out["R2"] = r1
    elif case_name == "Overhanging beam – right overhang with point load at free end":
        out["RA"] = r0
        out["RB"] = r1

    return out


def _normalize_support_condition(label: str | None) -> str:
    text = str(label or "").strip().replace("-", "–")
    known = {
        "Simply supported",
        "Pinned–Pinned",
        "Fixed–Pinned",
        "Pinned–Fixed",
        "Fixed–Fixed",
        "Fixed–Free",
    }
    if text in known:
        return text
    return "Simply supported"


def _single_span_moment_of_loads_about(
    x: float, point_loads: list[dict], udl_loads: list[dict]
) -> float:
    m = 0.0
    for pl in point_loads:
        xp = float(pl.get("x_m", 0.0) or 0.0)
        p = float(pl.get("P_kN", 0.0) or 0.0)
        if xp <= x:
            m += p * (x - xp)
    for udl in udl_loads:
        s = float(udl.get("x_start_m", 0.0) or 0.0)
        e = float(udl.get("x_end_m", 0.0) or 0.0)
        w = float(udl.get("w_kN_per_m", 0.0) or 0.0)
        left = min(max(s, 0.0), x)
        right = min(max(e, 0.0), x)
        if right <= left:
            continue
        length = right - left
        force = w * length
        centroid = left + 0.5 * length
        m += force * (x - centroid)
    return m


def _single_span_shear_at_x(x: float, left_reaction_kN: float, point_loads: list[dict], udl_loads: list[dict]) -> float:
    v = float(left_reaction_kN)
    for pl in point_loads:
        xp = float(pl.get("x_m", 0.0) or 0.0)
        p = float(pl.get("P_kN", 0.0) or 0.0)
        if xp <= x:
            v -= p
    for udl in udl_loads:
        s = float(udl.get("x_start_m", 0.0) or 0.0)
        e = float(udl.get("x_end_m", 0.0) or 0.0)
        w = float(udl.get("w_kN_per_m", 0.0) or 0.0)
        left = min(max(s, 0.0), x)
        right = min(max(e, 0.0), x)
        if right > left:
            v -= w * (right - left)
    return v


def _add_lumped_vertical_force(F: np.ndarray, x_nodes: np.ndarray, x_m: float, p_down_kN: float) -> None:
    n_nodes = x_nodes.size
    if n_nodes < 2:
        return
    x = max(float(x_nodes[0]), min(float(x_nodes[-1]), float(x_m)))
    if abs(x - float(x_nodes[-1])) < 1e-12:
        F[2 * (n_nodes - 1)] -= float(p_down_kN)
        return
    i = int(np.searchsorted(x_nodes, x, side="right") - 1)
    i = max(0, min(i, n_nodes - 2))
    x0 = float(x_nodes[i])
    x1 = float(x_nodes[i + 1])
    h = max(1e-12, x1 - x0)
    alpha = (x - x0) / h
    F[2 * i] -= float(p_down_kN) * (1.0 - alpha)
    F[2 * (i + 1)] -= float(p_down_kN) * alpha


def _hermite_N_at_xi(xi: float, h: float) -> tuple[float, float, float, float]:
    """Hermite transverse shape functions N1..N4 at ξ=x/h ∈ [0,1]; h=element length (m)."""
    xi = max(0.0, min(1.0, float(xi)))
    h = max(1e-12, float(h))
    n1 = 1.0 - 3.0 * xi * xi + 2.0 * xi * xi * xi
    n2 = h * (xi - 2.0 * xi * xi + xi * xi * xi)
    n3 = 3.0 * xi * xi - 2.0 * xi * xi * xi
    n4 = h * (-xi * xi + xi * xi * xi)
    return float(n1), float(n2), float(n3), float(n4)


def _hermite_udl_integral_vector(xi_a: float, xi_b: float, h: float) -> np.ndarray:
    """
    ∫_{xi_a}^{xi_b} [N1, N2, N3, N4]^T dξ  for ξ = x / h (fixed h).
    Used for consistent downward UDL: F -= w * h * radial integral.
    """
    xa, xb = float(min(xi_a, xi_b)), float(max(xi_a, xi_b))
    xa = max(0.0, min(1.0, xa))
    xb = max(0.0, min(1.0, xb))
    if xb <= xa + 1e-15:
        return np.zeros(4, dtype=float)
    h = max(1e-12, float(h))

    def _intn1(z: float) -> float:
        return z - z**3 + 0.5 * z**4

    def _intn2_over_h(z: float) -> float:
        return z * z / 2.0 - 2.0 * z**3 / 3.0 + z**4 / 4.0

    def _intn3(z: float) -> float:
        return z**3 - 0.5 * z**4

    def _intn4_over_h(z: float) -> float:
        return -z**3 / 3.0 + z**4 / 4.0

    i1 = _intn1(xb) - _intn1(xa)
    i2 = h * (_intn2_over_h(xb) - _intn2_over_h(xa))
    i3 = _intn3(xb) - _intn3(xa)
    i4 = h * (_intn4_over_h(xb) - _intn4_over_h(xa))
    return np.array([i1, i2, i3, i4], dtype=float)


def _refine_line_beam_mesh_for_fe(
    struct_x: np.ndarray,
    struct_supports: list[str],
    n_fe_per_span: int,
) -> tuple[np.ndarray, list[str]]:
    """
    Subdivide each structural span into uniform Euler–Bernoulli elements.
    Interior refinement nodes use support type ``internal`` (no translation/rotation restraint).
    """
    sx = np.asarray([float(v) for v in struct_x], dtype=float)
    if sx.size < 2:
        return sx, list(struct_supports)
    nseg = int(max(1, n_fe_per_span))
    out_x: list[float] = [float(sx[0])]
    out_s: list[str] = [str(struct_supports[0] or "internal")]
    for i in range(int(sx.size) - 1):
        xa, xb = float(sx[i]), float(sx[i + 1])
        hspan = xb - xa
        if hspan <= 1e-15:
            continue
        split = np.linspace(xa, xb, nseg + 1, dtype=float)
        for xv in split[1:-1]:
            out_x.append(float(xv))
            out_s.append("internal")
        out_x.append(xb)
        out_s.append(str(struct_supports[i + 1] or "internal"))
    return np.asarray(out_x, dtype=float), out_s


def _assemble_multispan_consistent_loads(
    F: np.ndarray, x_nodes: np.ndarray, pls: list, udls: list
) -> None:
    """
    Euler–Bernoulli Hermite beam: downward loads positive.
    Equivalent nodal load: F_i -= ∫ q N_i dx (positive q down, v DOF up) so bending is recovered.
    """
    n_nodes = int(x_nodes.size)
    if n_nodes < 2:
        return
    x0b = float(x_nodes[0])
    x1b = float(x_nodes[-1])
    tol = 1e-9

    for pl in pls:
        xp = max(x0b, min(x1b, float(pl.get("x_m", 0.0) or 0.0)))
        p = float(pl.get("P_kN", 0.0) or 0.0)
        if abs(p) < 1e-18:
            continue
        if xp >= x1b - tol:
            e = n_nodes - 2
            xi = 1.0
        elif xp <= x0b + tol:
            e = 0
            xi = 0.0
        else:
            e = int(np.searchsorted(x_nodes, xp, side="right") - 1)
            e = max(0, min(e, n_nodes - 2))
            xa = float(x_nodes[e])
            xb = float(x_nodes[e + 1])
            h = max(1e-12, xb - xa)
            xi = (xp - xa) / h
            xi = max(0.0, min(1.0, xi))
        xa = float(x_nodes[e])
        xb = float(x_nodes[e + 1])
        h = max(1e-12, xb - xa)
        n1, n2, n3, n4 = _hermite_N_at_xi(xi, h)
        dof0 = 2 * e
        F[dof0] -= p * n1
        F[dof0 + 1] -= p * n2
        F[dof0 + 2] -= p * n3
        F[dof0 + 3] -= p * n4

    for udl in udls:
        sg = max(x0b, min(x1b, float(udl.get("x_start_m", 0.0) or 0.0)))
        eg = max(x0b, min(x1b, float(udl.get("x_end_m", 0.0) or 0.0)))
        w = float(udl.get("w_kN_per_m", 0.0) or 0.0)
        if eg <= sg + tol or abs(w) < 1e-18:
            continue
        for e in range(n_nodes - 1):
            xa = float(x_nodes[e])
            xb = float(x_nodes[e + 1])
            h = max(1e-12, xb - xa)
            lo = max(xa, sg)
            hi = min(xb, eg)
            if hi <= lo + tol:
                continue
            xi_lo = (lo - xa) / h
            xi_hi = (hi - xa) / h
            vec = _hermite_udl_integral_vector(xi_lo, xi_hi, h)
            dof0 = 2 * e
            F[dof0 : dof0 + 4] -= w * h * vec


def _fixed_support_solver_single_span(
    L_m: float,
    support_condition: str,
    point_loads: list[dict],
    udl_loads: list[dict],
    n_points: int,
) -> dict:
    """
    One-span Euler-Bernoulli beam FE solver with end fixity options.
    Loads are applied as lumped nodal forces (sufficient for Phase 3 UI support options).
    """
    L = float(L_m)
    n_nodes = max(50, int(n_points))
    x_nodes = np.linspace(0.0, L, n_nodes, dtype=float)
    ndof = 2 * n_nodes
    K = np.zeros((ndof, ndof), dtype=float)
    F = np.zeros(ndof, dtype=float)
    EI = 1.0

    for e in range(n_nodes - 1):
        h = float(x_nodes[e + 1] - x_nodes[e])
        k = (EI / h**3) * np.array(
            [
                [12.0, 6.0 * h, -12.0, 6.0 * h],
                [6.0 * h, 4.0 * h**2, -6.0 * h, 2.0 * h**2],
                [-12.0, -6.0 * h, 12.0, -6.0 * h],
                [6.0 * h, 2.0 * h**2, -6.0 * h, 4.0 * h**2],
            ],
            dtype=float,
        )
        dof = [2 * e, 2 * e + 1, 2 * (e + 1), 2 * (e + 1) + 1]
        for i in range(4):
            for j in range(4):
                K[dof[i], dof[j]] += k[i, j]

    for pl in point_loads:
        x = max(0.0, min(L, float(pl.get("x_m", 0.0) or 0.0)))
        p = float(pl.get("P_kN", 0.0) or 0.0)
        _add_lumped_vertical_force(F, x_nodes, x, p)

    for udl in udl_loads:
        s = max(0.0, min(L, float(udl.get("x_start_m", 0.0) or 0.0)))
        e = max(0.0, min(L, float(udl.get("x_end_m", 0.0) or 0.0)))
        w = float(udl.get("w_kN_per_m", 0.0) or 0.0)
        if e <= s or abs(w) < 1e-12:
            continue
        for idx in range(n_nodes - 1):
            a = float(x_nodes[idx])
            b = float(x_nodes[idx + 1])
            overlap = min(b, e) - max(a, s)
            if overlap <= 0.0:
                continue
            x_centroid = max(a, s) + 0.5 * overlap
            _add_lumped_vertical_force(F, x_nodes, x_centroid, w * overlap)

    condition = _normalize_support_condition(support_condition)
    constraints: set[int] = set()
    if condition.startswith("Fixed"):
        constraints.update({0, 1})
    else:
        constraints.add(0)

    right_v = 2 * (n_nodes - 1)
    right_t = right_v + 1
    if condition.endswith("Fixed"):
        constraints.update({right_v, right_t})
    elif condition.endswith("Pinned"):
        constraints.add(right_v)

    constrained = np.array(sorted(constraints), dtype=int)
    free = np.array([i for i in range(ndof) if i not in constraints], dtype=int)
    u = np.zeros(ndof, dtype=float)
    if free.size > 0:
        K_ff = K[np.ix_(free, free)]
        F_f = F[free]
        u[free] = np.linalg.solve(K_ff, F_f)

    R = K @ u - F
    r_left = float(R[0])
    # Convert FE nodal rotation reaction sign to page convention (sagging positive, hogging negative).
    m_left = -float(R[1]) if 1 in constraints else 0.0
    r_right = float(R[right_v]) if right_v in constraints else 0.0
    m_right = float(R[right_t]) if right_t in constraints else 0.0

    x = x_nodes
    V = np.zeros_like(x)
    M = np.zeros_like(x)
    tol = 1e-9
    for i, xv in enumerate(x):
        if i == x.size - 1 and (condition.endswith("Pinned") or condition.endswith("Fixed")):
            # Keep legacy-like right-end station without adding the right vertical jump.
            x_eval = float(xv) - tol
        else:
            x_eval = float(xv)
        V[i] = _single_span_shear_at_x(x_eval, r_left, point_loads, udl_loads)
        M[i] = m_left + r_left * x_eval - _single_span_moment_of_loads_about(x_eval, point_loads, udl_loads)

    k_preview_n = int(min(6, K_ff.shape[0])) if "K_ff" in locals() else 0
    f_preview_n = int(min(10, F.size))
    u_preview_n = int(min(10, u.size))

    return {
        "x": x.tolist(),
        "V": V.tolist(),
        "M": M.tolist(),
        "reactions": {
            "R_left": r_left,
            "R_right": r_right,
            "M_left": m_left,
            "M_right": m_right,
        },
        "support_positions": [0.0, L],
        "metadata": {
            "mode": "single_span_fixed_solver",
            "support_condition": condition,
            "length_m": L,
            "node_positions_m": [float(v) for v in x_nodes.tolist()],
            "support_types": [
                "Fixed" if condition.startswith("Fixed") else "Pinned",
                "Fixed" if condition.endswith("Fixed") else "Pinned",
            ],
            "element_lengths_m": [float(v) for v in np.diff(x_nodes).tolist()],
            "restrained_dofs": [int(v) for v in constrained.tolist()],
            "free_dofs": [int(v) for v in free.tolist()],
            "global_size": int(ndof),
            "reduced_size": int(free.size),
            "global_F_preview": [float(v) for v in F[:f_preview_n].tolist()],
            "reduced_F_preview": [float(v) for v in (F[free][:k_preview_n] if free.size else np.array([])).tolist()],
            "reduced_u_preview": [float(v) for v in (u[free][:k_preview_n] if free.size else np.array([])).tolist()],
            "reduced_K_preview": [
                [float(xij) for xij in row]
                for row in (
                    (K_ff[:k_preview_n, :k_preview_n] if free.size else np.zeros((0, 0), dtype=float)).tolist()
                )
            ],
            "matrix_is_preview": True,
        },
    }


def solve_single_span_beam(
    L_m: float,
    support_condition: str,
    point_loads: list[dict] | None = None,
    udl_loads: list[dict] | None = None,
    n_points: int = 400,
) -> dict:
    """
    Single-span wrapper for Phase 3.
    Uses determinate solver for pinned-pinned / fixed-free and FE solver for indeterminate fixed-end options.
    """
    L = float(L_m)
    cond = _normalize_support_condition(support_condition)
    pls = list(point_loads or [])
    udls = list(udl_loads or [])

    if cond in ("Pinned–Pinned", "Simply supported"):
        supports = _two_span_vertical_supports(L, cond)
        model = BeamModel(
            length_m=L,
            supports=supports,
            point_loads=[
                PointLoad(max(0.0, min(L, float(pl.get("x_m", 0.0) or 0.0))), float(pl.get("P_kN", 0.0) or 0.0))
                for pl in pls
            ],
            udl_loads=[
                UDLLoad(
                    max(0.0, min(L, float(udl.get("x_start_m", 0.0) or 0.0))),
                    max(0.0, min(L, float(udl.get("x_end_m", 0.0) or 0.0))),
                    float(udl.get("w_kN_per_m", 0.0) or 0.0),
                )
                for udl in udls
            ],
        )
        res = solve_beam_model(model, n_points=n_points)
        return {
            "x": res.x,
            "V": res.V,
            "M": res.M,
            "reactions": {
                "R_left": float(res.metadata.get("R_left", 0.0)),
                "R_right": float(res.metadata.get("R_right", 0.0)),
                "M_left": 0.0,
                "M_right": 0.0,
            },
            "support_positions": [0.0, L],
            "metadata": {"mode": "single_span_determinate", "support_condition": cond, "length_m": L},
        }

    if cond == "Fixed–Free":
        model = BeamModel(
            length_m=L,
            supports=[Support(0.0, "fixed")],
            point_loads=[
                PointLoad(max(0.0, min(L, float(pl.get("x_m", 0.0) or 0.0))), float(pl.get("P_kN", 0.0) or 0.0))
                for pl in pls
            ],
            udl_loads=[
                UDLLoad(
                    max(0.0, min(L, float(udl.get("x_start_m", 0.0) or 0.0))),
                    max(0.0, min(L, float(udl.get("x_end_m", 0.0) or 0.0))),
                    float(udl.get("w_kN_per_m", 0.0) or 0.0),
                )
                for udl in udls
            ],
        )
        res = solve_beam_model(model, n_points=n_points)
        return {
            "x": res.x,
            "V": res.V,
            "M": res.M,
            "reactions": {
                "R_left": float(res.metadata.get("fixed_shear_kN", 0.0)),
                "R_right": 0.0,
                "M_left": float(res.metadata.get("fixed_moment_kNm", 0.0)),
                "M_right": 0.0,
            },
            "support_positions": [0.0],
            "metadata": {"mode": "single_span_determinate", "support_condition": cond, "length_m": L},
        }

    return _fixed_support_solver_single_span(
        L_m=L,
        support_condition=cond,
        point_loads=pls,
        udl_loads=udls,
        n_points=n_points,
    )


def _hermite_beam_transverse_m(
    local_x_m: float, L_m: float, v1: float, th1: float, v2: float, th2: float
) -> float:
    """Cubic Hermite transverse displacement at distance ``local_x_m`` from left node (m)."""
    if L_m <= 1e-12:
        return 0.0
    xi = local_x_m / L_m
    n1 = 1.0 - 3.0 * xi * xi + 2.0 * xi * xi * xi
    n2 = L_m * (xi - 2.0 * xi * xi + xi * xi * xi)
    n3 = 3.0 * xi * xi - 2.0 * xi * xi * xi
    n4 = L_m * (-xi * xi + xi * xi * xi)
    return float(n1 * v1 + n2 * th1 + n3 * v2 + n4 * th2)


def _beam_transverse_from_nodal_u_m(
    x_eval: float,
    x_nodes: np.ndarray,
    u_disp_m: np.ndarray,
) -> float:
    """Interpolate transverse displacement (m) at global ``x_eval`` from beam element nodal DOFs."""
    n = int(x_nodes.size)
    if n < 2:
        return 0.0
    xe = float(x_eval)
    if xe <= float(x_nodes[0]) + 1e-12:
        e = 0
    elif xe >= float(x_nodes[-1]) - 1e-12:
        e = n - 2
    else:
        e = int(np.searchsorted(x_nodes, xe, side="right") - 1)
        e = max(0, min(e, n - 2))
    xa = float(x_nodes[e])
    xb = float(x_nodes[e + 1])
    L = xb - xa
    loc = max(0.0, min(L, xe - xa))
    v1 = float(u_disp_m[2 * e])
    th1 = float(u_disp_m[2 * e + 1])
    v2 = float(u_disp_m[2 * (e + 1)])
    th2 = float(u_disp_m[2 * (e + 1) + 1])
    return _hermite_beam_transverse_m(loc, L, v1, th1, v2, th2)


def solve_beam_structure(
    node_positions_m: list[float],
    support_types: list[str],
    point_loads: list[dict] | None = None,
    udl_loads: list[dict] | None = None,
    n_points_per_span: int = 120,
    *,
    ei_knm2_for_deflection: float | None = None,
) -> dict:
    """
    General continuous-beam solver (2-5 spans expected from UI).
    Supports pinned/roller/fixed supports with mixed point loads and UDL segments.

    When ``ei_knm2_for_deflection`` is provided (flexural rigidity EI in kN·m²), the result
 includes ``w_mm``: elastic transverse displacement (mm) at each station in ``x`` matching
 the same load model used for ``V`` / ``M``. Internal stiffnesss is assembled with EI=1;
 nodal displacements are scaled by ``1/EI`` so ``w_mm`` matches real EI.
    """
    if len(node_positions_m) < 2:
        raise ValueError("At least two nodes are required")
    struct_x = np.asarray([float(x) for x in node_positions_m], dtype=float)
    if not np.all(np.diff(struct_x) > 0.0):
        raise ValueError("Node positions must be strictly increasing")
    if len(support_types) != struct_x.size:
        raise ValueError("support_types length must match node count")

    n_fe = int(max(2, min(160, int(n_points_per_span or 2))))
    x_nodes, support_types_refined = _refine_line_beam_mesh_for_fe(
        struct_x, list(support_types), n_fe
    )

    L_total = float(struct_x[-1] - struct_x[0])
    n_nodes = int(x_nodes.size)
    ndof = 2 * n_nodes
    K = np.zeros((ndof, ndof), dtype=float)
    F = np.zeros(ndof, dtype=float)
    EI = 1.0

    for e in range(n_nodes - 1):
        h = float(x_nodes[e + 1] - x_nodes[e])
        k = (EI / h**3) * np.array(
            [
                [12.0, 6.0 * h, -12.0, 6.0 * h],
                [6.0 * h, 4.0 * h**2, -6.0 * h, 2.0 * h**2],
                [-12.0, -6.0 * h, 12.0, -6.0 * h],
                [6.0 * h, 2.0 * h**2, -6.0 * h, 4.0 * h**2],
            ],
            dtype=float,
        )
        dof = [2 * e, 2 * e + 1, 2 * (e + 1), 2 * (e + 1) + 1]
        for i in range(4):
            for j in range(4):
                K[dof[i], dof[j]] += k[i, j]

    pls = list(point_loads or [])
    udls = list(udl_loads or [])
    _assemble_multispan_consistent_loads(F, x_nodes, pls, udls)

    constraints: set[int] = set()
    for i, st in enumerate(support_types_refined):
        t = str(st or "").strip().lower()
        v_dof = 2 * i
        r_dof = v_dof + 1
        if t in {"pinned", "roller", "fixed"}:
            constraints.add(v_dof)
        if t == "fixed":
            constraints.add(r_dof)

    constrained = np.array(sorted(constraints), dtype=int)
    free = np.array([i for i in range(ndof) if i not in constraints], dtype=int)
    u = np.zeros(ndof, dtype=float)
    if free.size > 0:
        K_ff = K[np.ix_(free, free)]
        F_f = F[free]
        u[free] = np.linalg.solve(K_ff, F_f)

    R = K @ u - F
    vertical_reactions: list[float] = []
    end_moments: list[float] = []
    for i, st in enumerate(support_types_refined):
        v_dof = 2 * i
        r_dof = v_dof + 1
        vertical_reactions.append(float(R[v_dof]) if v_dof in constraints else 0.0)
        if str(st or "").strip().lower() == "fixed" and r_dof in constraints:
            end_moments.append(-float(R[r_dof]))
        else:
            end_moments.append(0.0)

    x_segments: list[np.ndarray] = []
    n_struct = int(struct_x.size)
    for i in range(n_struct - 1):
        xa = float(struct_x[i])
        xb = float(struct_x[i + 1])
        x_seg = np.linspace(xa, xb, int(max(3, n_points_per_span)), dtype=float)
        if i > 0:
            x_seg = x_seg[1:]
        x_segments.append(x_seg)
    x = np.concatenate(x_segments) if x_segments else x_nodes.copy()
    V = np.zeros_like(x)
    M = np.zeros_like(x)
    tol = 1e-9

    for i, xv in enumerate(x):
        x_eval = float(xv)
        if i == x.size - 1:
            x_eval -= tol
        v_val = 0.0
        m_val = 0.0
        for sx, rv, rm in zip(x_nodes, vertical_reactions, end_moments):
            if float(sx) <= x_eval + tol:
                v_val += float(rv)
                m_val += float(rv) * (x_eval - float(sx))
                m_val += float(rm)
        for pl in pls:
            xp = float(pl.get("x_m", 0.0) or 0.0)
            p = float(pl.get("P_kN", 0.0) or 0.0)
            if xp <= x_eval + tol:
                v_val -= p
                m_val -= p * (x_eval - xp)
        for udl in udls:
            s = float(udl.get("x_start_m", 0.0) or 0.0)
            e = float(udl.get("x_end_m", 0.0) or 0.0)
            w = float(udl.get("w_kN_per_m", 0.0) or 0.0)
            right = min(e, x_eval)
            left = min(max(s, float(x_nodes[0])), right)
            if right <= left:
                continue
            length = right - left
            force = w * length
            centroid = left + 0.5 * length
            v_val -= force
            m_val -= force * (x_eval - centroid)
        V[i] = v_val
        M[i] = m_val

    reactions: dict[str, float] = {}
    struct_tol = 1e-6 + 1e-9 * max(1.0, L_total)
    for j, sx in enumerate(struct_x, start=1):
        idx = int(np.argmin(np.abs(x_nodes - float(sx))))
        if float(np.abs(x_nodes[idx] - float(sx))) <= struct_tol:
            reactions[f"R{j}"] = float(vertical_reactions[idx])
            if abs(end_moments[idx]) > 1e-9:
                reactions[f"M{j}"] = float(end_moments[idx])
        else:
            reactions[f"R{j}"] = 0.0

    out: dict = {
        "x": x.tolist(),
        "V": V.tolist(),
        "M": M.tolist(),
        "support_positions": [float(v) for v in struct_x.tolist()],
        "reactions": reactions,
        "metadata": {
            "mode": "multi_span_structure",
            "node_positions_m": [float(v) for v in struct_x.tolist()],
            "support_types": [str(v) for v in support_types],
            "fe_node_positions_m": [float(v) for v in x_nodes.tolist()],
            "fe_support_types": [str(v) for v in support_types_refined],
            "length_m": L_total,
            "element_lengths_m": [float(v) for v in np.diff(x_nodes).tolist()],
            "restrained_dofs": [int(v) for v in constrained.tolist()],
            "free_dofs": [int(v) for v in free.tolist()],
            "global_size": int(ndof),
            "reduced_size": int(free.size),
            "global_F": [float(v) for v in F.tolist()],
            "reduced_F": [float(v) for v in (F[free] if free.size else np.array([])).tolist()],
            "reduced_u": [float(v) for v in (u[free] if free.size else np.array([])).tolist()],
            "reduced_K": [
                [float(xij) for xij in row]
                for row in ((K[np.ix_(free, free)] if free.size else np.zeros((0, 0), dtype=float)).tolist())
            ],
            "matrix_is_preview": False,
        },
    }
    if ei_knm2_for_deflection is not None:
        try:
            ei = float(ei_knm2_for_deflection)
        except (TypeError, ValueError):
            ei = 0.0
        if ei > 0.0:
            u_disp = u / ei
            w_mm_list: list[float] = []
            for xv in x:
                w_m = _beam_transverse_from_nodal_u_m(float(xv), x_nodes, u_disp)
                w_mm_list.append(float(w_m * 1000.0))
            out["w_mm"] = w_mm_list
    return out


def validate_beam_result(result: BeamAnalysisResult) -> dict:
    """Quick sanity checks for debugging."""
    x = np.asarray(result.x, dtype=float)
    v = np.asarray(result.V, dtype=float)
    m = np.asarray(result.M, dtype=float)
    L = float(result.metadata.get("length_m", x[-1] if x.size else 0.0))
    supports = np.asarray(result.support_positions, dtype=float)
    report = {
        "n_x": int(x.size),
        "length_m": L,
        "max_abs_V": float(np.max(np.abs(v))) if v.size else 0.0,
        "max_abs_M": float(np.max(np.abs(m))) if m.size else 0.0,
        "all_finite_x": bool(np.all(np.isfinite(x))) if x.size else True,
        "all_finite_V": bool(np.all(np.isfinite(v))) if v.size else True,
        "all_finite_M": bool(np.all(np.isfinite(m))) if m.size else True,
        "supports_inside_or_at_ends": True,
    }
    if supports.size and L > 0:
        report["supports_inside_or_at_ends"] = bool(
            np.all((supports >= -1e-9) & (supports <= L + 1e-9))
        )
    return report
