"""Low-level, import-order-independent shear calculation contract.

This module owns the typed input/result boundary shared by ``shear_core`` and
``shear_checks_helpers``.  It deliberately has no dependency on either module,
so pure calculation consumers do not need the Streamlit-facing core to have
been imported first.
"""

from __future__ import annotations

from dataclasses import dataclass
import time

from calculations.shear import compute_shear_capacity_values
from state_runtime_gateway import speed_profile_record


@dataclass
class ShearInputs:
    b: float
    D: float
    d: float
    fc: float
    fsy: float
    Ec: float
    Es: float
    M_star: float
    V_star: float
    T_star: float
    N_star: float
    P_v: float
    phi: float
    sigma_cp: float
    A_st: float
    A_pt: float
    f_po: float
    A_ct: float
    d_g: float
    lig_d: float
    legs: float
    s_lig: float
    use_general_kv: bool
    sum_duct: float
    k_d: float


@dataclass
class ShearResults:
    # torsion cracking
    b_used: float
    D_used: float
    A_cp: float
    u_c: float
    Ao: float
    uh: float
    A_oh: float
    Tcr_kNm: float
    torsion_required: bool
    torsion_required_limit: float

    # equivalent shear
    Vt_eq_kN: float
    V_eq: float

    # effective web
    b_v: float
    d_v: float
    Asv: float
    f_syv: float

    # strain
    eps_x: float
    term_M: float
    sqrt_inner: float
    numerator: float

    # k_v and theta
    k_v: float
    theta_v_deg: float
    theta_v_rad: float

    # sectional shear
    sqrt_fc_limited: float
    Vuc_kN: float
    Vus_kN: float
    Vu_total_kN: float
    phi_Vu: float
    shear_ok: bool

    # web crushing
    Vu_max_kN: float
    LHS: float
    RHS: float
    web_ok: bool


def run_shear_calc(inp: ShearInputs) -> ShearResults:
    """Evaluate the pure shear capacity model and return its typed result."""

    started_at = time.perf_counter()
    values = compute_shear_capacity_values(inp)
    result = ShearResults(**values)
    speed_profile_record(
        "derived_result_computation.shear_capacity.run_shear_calc",
        (time.perf_counter() - started_at) * 1000.0,
        category="compute",
    )
    return result


__all__ = ["ShearInputs", "ShearResults", "run_shear_calc"]
