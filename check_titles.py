from __future__ import annotations

import re


def format_check_title(number: str, title: str) -> str:
    return f"Check {number} — {title}"


def strip_check_prefix(label: str) -> str:
    txt = str(label or "").strip()
    return re.sub(r"^Check\s+\d+(?:\.\d+)?\s+—\s*", "", txt)


BENDING_CHECK_TITLES = {
    "bend_strength": format_check_title("1", "Flexural strength capacity"),
    "bend_strength_pos": format_check_title("1.1", "Positive bending"),
    "bend_strength_neg": format_check_title("1.2", "Negative bending"),
    "bend_Asmin": format_check_title("2", "Minimum tensile reinforcement"),
    "bend_min_strength": format_check_title("3", "Minimum design capacity requirement"),
    "bend_duct": format_check_title("4", "Ductility limit"),
    "bend_sls_stress": format_check_title("5", "Steel stress at serviceability"),
    "bend_service_moment": format_check_title("6", "Service bending moment"),
}

SHEAR_CHECK_TITLES = {
    "shear_check1": format_check_title("1", "Torsion cracking check"),
    "shear_check2": format_check_title("2", "Equivalent design shear"),
    "shear_check3": format_check_title("3", "Shear-resisting section"),
    "shear_check4": format_check_title("4", "Longitudinal strain"),
    "shear_check5": format_check_title("5", "Shear model parameters"),
    "shear_check6": format_check_title("6", "Concrete shear strength"),
    "shear_check7": format_check_title("7", "Steel shear strength"),
    "shear_check8": format_check_title("8", "Sectional shear capacity"),
    "shear_check9": format_check_title("9", "Web-crushing strength"),
    "shear_check10": format_check_title("10", "Shear reinforcement layout"),
    "shear_check11": format_check_title("11", "Minimum shear reinforcement"),
    "shear_check12": format_check_title("12", "Detailing and deep-beam considerations"),
}

CRACK_CHECK_TITLES = {
    "crk_step_1": format_check_title("1", "Inputs and crack limits"),
    "crk_step_2": format_check_title("2", "Table-based crack control check"),
    "crk_step_3": format_check_title("3", "Direct crack width check"),
    "crk_step_4": format_check_title("4", "Governing outcome"),
}

DEFLECTION_CHECK_TITLES = {
    "defl_total": format_check_title("1", "Total deflection (short + long-term)"),
    "defl_short": format_check_title("2", "Short-term deflection (total load)"),
    "defl_long": format_check_title("3", "Additional long-term deflection"),
}

CREEP_CHECK_TITLES = {
    "creep_phi_cc_t": format_check_title("1", "Design creep coefficient ϕ_cc(t)"),
    "creep_phi_cc_table": format_check_title("2", "Final creep coefficient ϕ*cc (30y, table)"),
    "creep_eps_cc": format_check_title("3", "Creep strain ε_cc(t)"),
}

SHRINKAGE_CHECK_TITLES = {
    "shrinkage_autogenous": format_check_title("1", "Autogenous shrinkage ε_cse"),
    "shrinkage_drying": format_check_title("2", "Drying shrinkage ε_csd"),
    "shrinkage_total": format_check_title("3", "Total shrinkage ε_cs"),
}
