"""Pure explanatory evidence for the authoritative ULS neutral-axis result."""

from __future__ import annotations

import math


def neutral_axis_hand_solution(
    *, b: float, D: float, fc: float, fsy: float, Es: float,
    alpha2: float, gamma: float, dn: float, block_depth: float,
    layer_areas: tuple[float, ...], layer_depths: tuple[float, ...],
    layer_stresses: tuple[float, ...], layer_labels: tuple[str, ...],
    section_shape: str, eps_cu: float = 0.003,
) -> dict:
    """Derive hand algebra from—without replacing—the accepted solver state."""

    count = min(len(layer_areas), len(layer_depths), len(layer_stresses))
    eps_sy = fsy / Es if Es > 0.0 else float("nan")
    kc = alpha2 * fc * b * gamma
    ty = cy = sum_q = sum_qy = displaced = 0.0
    rows: list[dict] = []
    regimes = []
    for index in range(count):
        area = float(layer_areas[index])
        depth = float(layer_depths[index])
        stress = float(layer_stresses[index])
        label = layer_labels[index] if index < len(layer_labels) else f"Layer {index + 1}"
        strain = -eps_cu * (depth - dn) / dn if dn > 1e-12 else float("nan")
        yielded = abs(stress) >= max(0.0, fsy - 1e-6)
        state = (
            "yielded tension" if yielded and stress < 0.0
            else "yielded compression" if yielded and stress > 0.0
            else "elastic tension" if stress < 0.0
            else "elastic compression" if stress > 0.0
            else "approximately zero stress"
        )
        q = area * Es * eps_cu if not yielded else 0.0
        if yielded and stress < 0.0:
            ty += area * fsy
            contribution = "$T_y$"
        elif yielded and stress > 0.0:
            cy += area * fsy
            contribution = "$C_y$"
        else:
            sum_q += q
            sum_qy += q * depth
            contribution = f"$Q_{{{index + 1}}},\\;Q_{{{index + 1}}}y_{{{index + 1}}}$"
        inside_block = depth <= block_depth + 1e-9
        raw_force = area * stress
        displaced_force = area * alpha2 * fc if inside_block else 0.0
        net_force = raw_force - displaced_force
        if inside_block:
            displaced += displaced_force
        boundary = depth / (1.0 + eps_sy / eps_cu) if math.isfinite(eps_sy) and eps_cu > 0.0 else float("nan")
        rows.append({
            "index": index + 1, "label": label, "area": area,
            "depth": depth, "stress": stress, "strain": strain,
            "state": state, "q": q, "qy": q * depth,
            "yield_boundary": boundary, "inside_block": inside_block,
            "raw_force": raw_force, "displaced_force": displaced_force,
            "net_force": net_force,
            "contribution": contribution,
        })
        regimes.append((yielded, -1 if stress < 0.0 else 1 if stress > 0.0 else 0, inside_block))

    A = kc
    B = cy - ty + sum_q - displaced
    C = -sum_qy
    linear = abs(sum_q) <= 1e-12
    roots: tuple[float, ...] = ()
    if section_shape == "RECT":
        if linear and abs(A) > 1e-12:
            roots = (-B / A,)
        elif abs(A) > 1e-12:
            discriminant = B * B - 4.0 * A * C
            if discriminant >= 0.0:
                delta = math.sqrt(discriminant)
                roots = ((-B + delta) / (2.0 * A), (-B - delta) / (2.0 * A))

    def regime_is_valid(candidate: float) -> bool:
        if not (math.isfinite(candidate) and 0.0 < candidate < D):
            return False
        candidate_block = gamma * candidate
        for row, expected in zip(rows, regimes):
            trial = Es * eps_cu * (candidate - row["depth"]) / candidate
            trial = max(-fsy, min(fsy, trial))
            actual = (
                abs(trial) >= max(0.0, fsy - 1e-6),
                -1 if trial < 0.0 else 1 if trial > 0.0 else 0,
                row["depth"] <= candidate_block + 1e-9,
            )
            if actual != expected:
                return False
        return True

    root_checks = tuple((root, regime_is_valid(root)) for root in roots)
    reproduced = any(valid and abs(root - dn) <= max(1e-6, 1e-6 * abs(dn)) for root, valid in root_checks)
    return {
        "eps_cu": eps_cu, "eps_sy": eps_sy, "kc": kc,
        "ty": ty, "cy": cy, "sum_q": sum_q, "sum_qy": sum_qy,
        "displaced": displaced, "A": A, "B": B, "C": C,
        "rows": rows, "linear": linear, "roots": root_checks,
        "reproduced": reproduced,
        "polynomial_at_dn": A * dn * dn + B * dn + C,
        "section_shape": section_shape,
    }


__all__ = ["neutral_axis_hand_solution"]
