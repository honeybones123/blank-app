"""Compatibility imports for the installed authoritative time-dependent engine.

The Streamlit Creep and Shrinkage pages retain their established presentation
code, but no longer own a second copy of the AS 3600 equations.  All numerical
functions below come from the same installed V2 calculation package used by
the Inputs summaries and Design Brain.
"""

from inputs_v2.engineering.time_dependent_concrete import (  # noqa: F401
    BASIC_CREEP_COEFF,
    CREEP_ENV_LABELS,
    CREEP_FINAL_TABLE,
    ENV_LABELS,
    SHRINKAGE_ENV_LABELS,
    SHRINKAGE_TABLE,
    autogenous_shrinkage_final_from_current,
    basic_creep_coeff,
    calc_eps_cse,
    calc_k1_shrinkage,
    calc_k2_creep,
    calc_k3,
    calc_k4,
    calc_k5,
    calc_k6,
    creep_alpha2_from_th,
    creep_closest_fc_row,
    creep_closest_th,
    creep_coefficient_value,
    creep_strain_values,
    exposed_perimeter_geometry_values,
    final_creep_coeff_table,
    shrinkage_closest_fc_row,
    shrinkage_closest_th,
    shrinkage_eps_final,
    shrinkage_total_values,
    sustained_creep_stress_mpa,
)

_creep_closest_fc_row = creep_closest_fc_row
_creep_closest_th = creep_closest_th
_shrinkage_closest_fc_row = shrinkage_closest_fc_row
_shrinkage_closest_th = shrinkage_closest_th
_shrinkage_eps_final = shrinkage_eps_final


__all__ = [name for name in globals() if not name.startswith("__")]
