"""
Zoned shear link spacing from a shear demand envelope (detailing aid).

Uses sectional inputs from the existing shear check (V_uc, θ_v, d_v, f_syv, A_sv)
without modifying shear_core or check formulas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

EnvelopeKind = Literal["ss_udl", "cantilever_udl", "uniform"]


@dataclass(frozen=True)
class ZoneSpacingSegment:
    """One coloured strip along the beam for UI."""

    x0_m: float
    x1_m: float
    label: str
    s_mm: float
    asv_over_s_req_max: float
    color: str  # rgba


@dataclass(frozen=True)
class ZoneSpacingDesign:
    segments: tuple[ZoneSpacingSegment, ...]
    summary_lines: tuple[str, ...]
    warnings: tuple[str, ...]
    s_max_code_mm: float
    s_min_practical_mm: float
    envelope_kind: EnvelopeKind
    legs: float


def _cot(theta_rad: float) -> float:
    t = math.tan(theta_rad)
    return 1.0 / t if abs(t) > 1e-12 else 0.0


def asv_over_s_required_mm(
    V_star_kN: float,
    Vuc_kN: float,
    f_syv_mpa: float,
    d_v_mm: float,
    cot_theta_v: float,
) -> float:
    """Required A_sv / s (mm²/mm) for truss model; non-negative."""
    v_n = max(0.0, (max(V_star_kN, 0.0) - max(Vuc_kN, 0.0)) * 1e3)
    denom = max(f_syv_mpa * d_v_mm * cot_theta_v, 1e-9)
    return v_n / denom


def asv_min_over_s_mm(fc_mpa: float, b_v_mm: float, f_syv_mpa: float) -> float:
    return 0.08 * math.sqrt(max(fc_mpa, 0.1)) * b_v_mm / max(f_syv_mpa, 1e-9)


def code_s_max_mm(d_mm: float) -> float:
    """AS 3600 typical cap: min(0.75 d, 500 mm)."""
    return min(0.75 * max(d_mm, 1e-6), 500.0)


def practical_s_min_mm(lig_d_mm: float) -> float:
    return max(25.0, 1.5 * max(lig_d_mm, 1.0))


def snap_spacing_down_mm(s_raw_mm: float, increment_mm: float, s_min_mm: float, s_max_mm: float) -> float:
    """Round down to increment so capacity is not reduced vs raw maximum spacing."""
    s_cap = min(s_max_mm, max(s_min_mm, s_raw_mm))
    n = math.floor(s_cap / increment_mm + 1e-9)
    return max(s_min_mm, min(s_max_mm, n * increment_mm))


def _normalize_envelope_ss_udl(x: np.ndarray, L: float) -> np.ndarray:
    """|V(x)| / V_max for simply supported UDL; max at supports."""
    half = max(L / 2.0, 1e-12)
    return np.abs(1.0 - 2.0 * np.abs(x - L / 2.0) / L)


def _normalize_envelope_cantilever_udl(x: np.ndarray, L: float) -> np.ndarray:
    """|V(x)| / V_max; fixed at x=0, free at x=L; UDL."""
    Ls = max(L, 1e-12)
    return (Ls - x) / Ls


def _merge_intervals(raw: list[tuple[float, float, str]]) -> list[tuple[float, float, str]]:
    raw = sorted((max(0.0, a), max(0.0, b), z) for a, b, z in raw if b > a + 1e-12)
    out: list[tuple[float, float, str]] = []
    for a, b, z in raw:
        if out and out[-1][2] == z and abs(a - out[-1][1]) < 1e-9:
            out[-1] = (out[-1][0], b, z)
        else:
            out.append((a, b, z))
    return out


def _zone_intervals_ss(L_m: float, dv_m: float) -> list[tuple[float, float, str]]:
    """
    Simply supported, symmetric: support strips (1.5 d_v), shear span sides, mid third low-shear.
    Coordinates in metres along [0, L].
    """
    L = max(L_m, 1e-9)
    w1 = min(1.5 * dv_m, max(L / 2.0 - 1e-9, 0.0))
    C = L - 2.0 * w1
    if C <= 1e-9:
        return _merge_intervals([(0.0, L, "z2")])
    c3 = C / 3.0
    z3_lo = w1 + c3
    z3_hi = w1 + 2.0 * c3
    return _merge_intervals(
        [
            (0.0, w1, "z1"),
            (w1, z3_lo, "z2"),
            (z3_lo, z3_hi, "z3"),
            (z3_hi, L - w1, "z2"),
            (L - w1, L, "z1"),
        ]
    )


def _zone_intervals_cantilever(L_m: float, dv_m: float) -> list[tuple[float, float, str]]:
    L = max(L_m, 1e-9)
    w1 = min(1.5 * dv_m, L * 0.45)
    z3_start = max(w1, 0.55 * L)
    out: list[tuple[float, float, str]] = [(0.0, w1, "z1")]
    if z3_start < L - 1e-9:
        out.append((w1, z3_start, "z2"))
        out.append((z3_start, L, "z3"))
    else:
        out.append((w1, L, "z2"))
    return _merge_intervals(out)


def _zone_color(zid: str) -> str:
    return {
        "z1": "rgba(200,45,45,0.55)",  # red tight
        "z2": "rgba(255,152,0,0.50)",  # orange
        "z3": "rgba(46,125,50,0.45)",  # green wide
    }.get(zid, "rgba(120,120,120,0.35)")


def compute_zoned_shear_spacing(
    *,
    L_m: float,
    d_mm: float,
    D_mm: float,
    d_v_mm: float,
    b_v_mm: float,
    fc_mpa: float,
    f_syv_mpa: float,
    V_eq_kN: float,
    Vuc_kN: float,
    theta_v_rad: float,
    Asv_mm2: float,
    lig_d_mm: float,
    legs: float,
    is_cantilever: bool,
    envelope: EnvelopeKind | None = None,
    n_samples: int = 241,
    spacing_increment_mm: float = 25.0,
) -> ZoneSpacingDesign | None:
    """
    Build 3-zone stepped spacing. Returns None if legs < 2 or Asv <= 0.
    """
    if legs < 2 or Asv_mm2 <= 1e-9:
        return None
    L = max(L_m, 1e-9)
    dv_m = d_v_mm / 1000.0
    cot_t = _cot(theta_v_rad)
    rho_min = asv_min_over_s_mm(fc_mpa, b_v_mm, f_syv_mpa)
    s_max = code_s_max_mm(d_mm)
    s_min = practical_s_min_mm(lig_d_mm)

    if envelope is None:
        env: EnvelopeKind = "cantilever_udl" if is_cantilever else "ss_udl"
    else:
        env = envelope

    xs = np.linspace(0.0, L, n_samples)

    if env == "uniform":
        v_ratio = np.ones_like(xs)
    elif env == "cantilever_udl":
        v_ratio = _normalize_envelope_cantilever_udl(xs, L)
    else:
        v_ratio = _normalize_envelope_ss_udl(xs, L)

    v_max = float(np.max(v_ratio)) if v_ratio.size else 1.0
    if v_max < 1e-12:
        v_ratio = np.ones_like(xs)
        v_max = 1.0
    v_kn = (v_ratio / v_max) * max(V_eq_kN, 0.0)

    req = np.array(
        [
            max(
                rho_min,
                asv_over_s_required_mm(float(vk), Vuc_kN, f_syv_mpa, d_v_mm, cot_t),
            )
            for vk in v_kn
        ]
    )

    if is_cantilever:
        intervals = _zone_intervals_cantilever(L, dv_m)
    else:
        intervals = _zone_intervals_ss(L, dv_m)

    zone_req: dict[str, float] = {"z1": 0.0, "z2": 0.0, "z3": 0.0}
    for a, b, zid in intervals:
        mask = (xs >= a - 1e-12) & (xs <= b + 1e-12)
        if not np.any(mask):
            continue
        m = float(np.max(req[mask]))
        zone_req[zid] = max(zone_req.get(zid, 0.0), m)

    # Enforce non-increasing spacing toward midspan for symmetric SS (z1 >= z2 >= z3 demand)
    if not is_cantilever:
        zone_req["z2"] = max(zone_req["z2"], zone_req["z3"])
        zone_req["z1"] = max(zone_req["z1"], zone_req["z2"])

    zone_s: dict[str, float] = {}
    warnings: list[str] = []
    for zid, rho in zone_req.items():
        if rho <= 1e-12:
            zone_s[zid] = s_max
            continue
        s_raw = Asv_mm2 / rho
        s_use = snap_spacing_down_mm(s_raw, spacing_increment_mm, s_min, s_max)
        prov = Asv_mm2 / s_use
        if prov + 1e-9 < rho:
            s_use = snap_spacing_down_mm(s_raw, 10.0, s_min, s_max)
            prov = Asv_mm2 / s_use
        if prov + 1e-9 < rho:
            warnings.append(
                f"Zone {zid}: provided $A_{{sv}}/s$ may be below envelope maximum; "
                "increase bar size or number of legs."
            )
        zone_s[zid] = s_use
        if s_use <= s_min + 0.5:
            warnings.append(
                "Spacing is at or below the practical minimum; verify aggregate size and constructability."
            )

    segments: list[ZoneSpacingSegment] = []
    summary_lines: list[str] = []
    legs_i = int(round(legs)) if abs(legs - round(legs)) < 0.01 else int(legs)

    for a, b, zid in intervals:
        s_mm = zone_s.get(zid, s_max)
        rho_m = zone_req.get(zid, rho_min)
        segments.append(
            ZoneSpacingSegment(
                x0_m=a,
                x1_m=b,
                label=f"Zone {zid[-1]}",
                s_mm=s_mm,
                asv_over_s_req_max=rho_m,
                color=_zone_color(zid),
            )
        )

    # Human-readable ranges (mm along span)
    dv_mm = d_v_mm
    Lmm = L * 1000.0
    z1w = min(1.5 * dv_mm, Lmm / 2.0)
    if is_cantilever:
        summary_lines.append(f"0–{z1w:.0f} mm (≈1.5$d_v$): {legs_i} legs @ {zone_s.get('z1', s_max):.0f} mm")
        summary_lines.append(f"{z1w:.0f} mm–tip: {legs_i} legs @ {zone_s.get('z2', s_max):.0f} mm")
        if "z3" in zone_s and intervals[-1][2] == "z3":
            summary_lines.append(f"Low-shear tail: {legs_i} legs @ {zone_s.get('z3', s_max):.0f} mm")
    else:
        summary_lines.append(f"0–{z1w:.0f} mm & mirror (support): {legs_i} legs @ {zone_s.get('z1', s_max):.0f} mm")
        summary_lines.append(f"{z1w:.0f} mm–$L/2$ & mirror (shear span): {legs_i} legs @ {zone_s.get('z2', s_max):.0f} mm")
        summary_lines.append(f"Midspan band: {legs_i} legs @ {zone_s.get('z3', s_max):.0f} mm")

    return ZoneSpacingDesign(
        segments=tuple(segments),
        summary_lines=tuple(summary_lines),
        warnings=tuple(dict.fromkeys(warnings)),
        s_max_code_mm=s_max,
        s_min_practical_mm=s_min,
        envelope_kind=env,
        legs=float(legs),
    )


