"""Calculation-driving input inventory for the copied V1 formulas.

This is deliberately data-only: it documents the public V2 edit surface and
keeps legacy names confined to the adapter.
"""

CALCULATION_INPUT_INVENTORY = (
    {"field": "width_mm", "unit": "mm", "family": "geometry", "visibility": "always"},
    {"field": "depth_mm", "unit": "mm", "family": "geometry", "visibility": "always"},
    {"field": "span_mm", "unit": "mm", "family": "geometry", "visibility": "always"},
    {"field": "section_shape", "unit": "enum", "family": "geometry", "visibility": "always"},
    {"field": "actions.bending_moment_knm", "unit": "kNm", "family": "bending", "visibility": "detailed"},
    {"field": "actions.torsion_knm", "unit": "kNm", "family": "shear", "visibility": "detailed"},
    {"field": "actions.shear_force_kn", "unit": "kN", "family": "shear", "visibility": "detailed"},
    {"field": "actions.axial_force_kn", "unit": "kN", "family": "bending", "visibility": "detailed"},
    {"field": "bottom", "unit": "mm/count", "family": "bending", "visibility": "always"},
    {"field": "top", "unit": "mm/count", "family": "bending", "visibility": "always"},
    {"field": "shear", "unit": "mm/count", "family": "shear", "visibility": "always"},
    {"field": "materials", "unit": "MPa", "family": "all", "visibility": "always"},
    {"field": "supports", "unit": "enum", "family": "deflection", "visibility": "detailed"},
    {"field": "time_dependent", "unit": "days", "family": "creep_shrinkage", "visibility": "detailed"},
    {"field": "voids", "unit": "mm/count", "family": "shear", "visibility": "detailed"},
    {"field": "deflection", "unit": "enum/mm", "family": "deflection", "visibility": "detailed"},
)
