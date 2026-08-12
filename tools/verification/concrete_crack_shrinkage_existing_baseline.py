"""Regression lock for the existing AS 3600 crack-control and shrinkage path.

This verifier intentionally exercises the current pure calculation functions. It
does not introduce method selection or change any production calculation path.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from calculations.crack_control import compute_crack_control_values
from calculations.creep_shrinkage import (
    calc_eps_cse,
    calc_k1_shrinkage,
    exposed_perimeter_geometry_values,
    shrinkage_closest_th,
    shrinkage_eps_final,
    shrinkage_total_values,
)


def _assert_close(actual: float, expected: float, *, name: str) -> None:
    if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise AssertionError(f"{name}: expected {expected!r}, got {actual!r}")


def main() -> None:
    geometry = exposed_perimeter_geometry_values(
        400.0, 600.0, "Beam \u2013 three faces exposed"
    )
    thickness_table_mm = shrinkage_closest_th(geometry["th_raw"])
    eps_cse = calc_eps_cse(32.0, 365.0)
    eps_csd_final = shrinkage_eps_final(
        32.0, "Temperate inland environment", thickness_table_mm
    )
    k1 = calc_k1_shrinkage(365.0, thickness_table_mm)
    shrinkage = shrinkage_total_values(
        k1=k1,
        eps_cse=eps_cse,
        eps_csd_final=eps_csd_final,
    )

    _assert_close(geometry["Ag"], 240_000.0, name="shrinkage.area_mm2")
    _assert_close(geometry["ue"], 1_600.0, name="shrinkage.exposed_perimeter_mm")
    _assert_close(geometry["th_raw"], 300.0, name="shrinkage.notional_thickness_raw_mm")
    _assert_close(thickness_table_mm, 200.0, name="shrinkage.notional_thickness_table_mm")
    _assert_close(k1, 0.979469462525669, name="shrinkage.k1")
    _assert_close(eps_cse * 1e6, 86.99996029732061, name="shrinkage.eps_cse_micro")
    _assert_close(eps_csd_final * 1e6, 520.0, name="shrinkage.eps_csd_final_micro")
    _assert_close(shrinkage["eps_csd_t"] * 1e6, 509.3241205133478, name="shrinkage.eps_csd_t_micro")
    _assert_close(shrinkage["eps_cs_total_micro"], 596.3240808106684, name="shrinkage.eps_cs_total_micro")

    crack = compute_crack_control_values(
        b=300.0,
        D=600.0,
        c=40.0,
        db=20.0,
        spacing=200.0,
        Ast=942.477796,
        fc=32.0,
        Ec=30_000.0,
        Es=200_000.0,
        fsy=500.0,
        wmax_choice=0.3,
        member_type="Flexure",
        sigma_sr=200.0,
        phi_ce=2.0,
        eps_cs=shrinkage["eps_cs_total"],
        k1=0.8,
        k2=0.5,
    )

    _assert_close(crack["Aceff"], 15_000.0, name="crack.aceff")
    _assert_close(crack["rho_eff"], 0.06283185306666667, name="crack.rho_eff")
    _assert_close(crack["sigma_allow_table"], 225.0, name="crack.sigma_allow_table")
    _assert_close(crack["utilisation_table"], 0.8888888888888888, name="crack.utilisation_table")
    _assert_close(crack["eps_diff"], 0.0012306203909074344, name="crack.eps_diff")
    _assert_close(crack["sr_max"], 174.19718634517307, name="crack.sr_max")
    _assert_close(crack["w_calc"], 0.2143706095550721, name="crack.w_calc")
    _assert_close(crack["utilisation_w"], 0.714568698516907, name="crack.utilisation_w")
    if not crack["passes_table"] or not crack["passes_w"]:
        raise AssertionError("Existing AS 3600 crack-control baseline should pass")

    print("PASS: existing AS 3600 crack-control and shrinkage baseline is unchanged")


if __name__ == "__main__":
    main()
