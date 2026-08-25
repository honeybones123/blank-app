"""Pure report projection for the authoritative Shear calculation result."""

from __future__ import annotations

import math
from typing import Any


def build_shear_report(
    *,
    results: Any,
    phi: float,
    phi_Vu_cap: float,
    util: float,
    Vu_star: float,
    Tu_star: float,
    s_lig: float,
    Asv_over_s: float,
    Asv_min_over_s: float,
    max_spacing: float,
    min_shear_ok: bool,
    spacing_ok: bool,
) -> dict[str, Any]:
    """Build the existing Shear report tree without owning page/session state."""

    # Summary for report
    summary = [
        ("Demand", f"{results.V_eq:.1f} kN"),
        ("Capacity", f"{phi_Vu_cap:.1f} kN"),
        ("Utilisation", f"{util:.2f}" if not math.isnan(util) else "—"),
        ("Outcome", "PASS" if util <= 1.0 else "FAIL"),
    ]

    boxes = []

    boxes.append({
        "id": "1",
        "title": "Actions",
        "clause": "AS 3600:2018 Cl. 2.3",
        "derivation": "<br/>".join([
            f"V* = {Vu_star:.1f} kN",
            f"T* = {Tu_star:.1f} kNm",
            f"V_eq* = {results.V_eq:.1f} kN",
        ]),
        "result": "",
        "status": None,
        "diagram": None,
    })

    boxes.append({
        "id": "2",
        "title": "Effective section + reinforcement",
        "clause": "AS 3600:2018 Cl. 8.2.2",
        "derivation": "<br/>".join([
            f"b_v = {results.b_v:.0f} mm",
            f"d_v = {results.d_v:.0f} mm",
            f"A_sv = {results.Asv:.0f} mm²",
            f"Provided link spacing s = {s_lig:.0f} mm",
        ]),
        "result": "",
        "status": None,
        "diagram": None,
    })

    boxes.append({
        "id": "3",
        "title": "MCFT parameters",
        "clause": "AS 3600:2018 Cl. 8.2.4",
        "derivation": "<br/>".join([
            f"εx = {results.eps_x:.5f}",
            f"k_v = {results.k_v:.3f}",
            f"θ_v = {results.theta_v_deg:.1f}°",
        ]),
        "result": "",
        "status": None,
        "diagram": None,
    })

    boxes.append({
        "id": "4",
        "title": "Concrete shear capacity",
        "clause": "AS 3600:2018 Cl. 8.2.4.1",
        "derivation": "<br/>".join([
            f"b_v = {results.b_v:.0f} mm",
            f"d_v = {results.d_v:.0f} mm",
            f"V_uc = {results.Vuc_kN:.1f} kN",
        ]),
        "result": f"φV_uc = {(phi * results.Vuc_kN):.1f} kN",
        "status": None,
        "diagram": None,
    })

    boxes.append({
        "id": "5",
        "title": "Shear reinforcement contribution",
        "clause": "AS 3600:2018 Cl. 8.2.5",
        "derivation": "<br/>".join([
            f"A_sv = {results.Asv:.0f} mm²",
            f"Provided link spacing s = {s_lig:.0f} mm",
            f"V_us = {results.Vus_kN:.1f} kN",
        ]),
        "result": f"φV_us = {(phi * results.Vus_kN):.1f} kN",
        "status": None,
        "diagram": None,
    })

    boxes.append({
        "id": "6",
        "title": "Total shear capacity and utilisation",
        "clause": "AS 3600:2018",
        "derivation": "<br/>".join([
            f"φV_u = {phi_Vu_cap:.1f} kN",
            f"Util = V_eq*/(φV_u) = {util:.2f}" if not math.isnan(util) else "Util = —",
        ]),
        "result": "PASS" if util <= 1.0 else "FAIL",
        "status": "pass" if util <= 1.0 else "fail",
        "diagram": None,
    })

    boxes.append({
        "id": "7",
        "title": "Web-crushing limit",
        "clause": "AS 3600:2018 Cl. 8.2.6",
        "derivation": "<br/>".join([
            f"V_u,max = {results.Vu_max_kN:.1f} kN",
            f"Demand = {results.LHS:.1f}",
            f"Capacity = {results.RHS:.1f}",
        ]),
        "result": "PASS" if results.web_ok else "FAIL",
        "status": "pass" if results.web_ok else "fail",
        "diagram": None,
    })

    boxes.append({
        "id": "8",
        "title": "Minimum shear reinforcement + spacing",
        "clause": "AS 3600:2018 Cl. 8.2.5",
        "derivation": "<br/>".join([
            f"A_sv/s = {Asv_over_s:.3f} mm²/mm",
            f"(A_sv/s)_min = {Asv_min_over_s:.3f} mm²/mm",
            f"s_max = {max_spacing:.0f} mm",
        ]),
        "result": "PASS" if (min_shear_ok and spacing_ok) else "FAIL",
        "status": "pass" if (min_shear_ok and spacing_ok) else "fail",
        "diagram": None,
    })

    shear_report = {
        "module_title": "Shear (ULS)",
        "summary": summary,
        "tabs": [{"tab_title": "ULS Checks", "boxes": boxes}],
    }


    return shear_report


__all__ = ["build_shear_report"]

