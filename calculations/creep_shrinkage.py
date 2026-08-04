from __future__ import annotations

import math


# AS 3600:2018 Table 3.1.8.2 - Basic creep coefficient.
BASIC_CREEP_COEFF = {
    20: 5.2,
    25: 4.2,
    32: 3.4,
    40: 2.8,
    50: 2.4,
    65: 2.0,
    80: 1.7,
    100: 1.5,
}

# AS 3600:2018 Table 3.1.8.3 - Final creep coefficient after 30 years.
CREEP_FINAL_TABLE = {
    25: {
        "Arid": {100: 4.82, 200: 3.90, 400: 3.27},
        "Interior": {100: 4.48, 200: 3.62, 400: 3.03},
        "Temperate": {100: 4.13, 200: 3.34, 400: 2.80},
        "Tropical": {100: 3.44, 200: 2.78, 400: 2.33},
    },
    32: {
        "Arid": {100: 3.90, 200: 3.15, 400: 2.64},
        "Interior": {100: 3.62, 200: 2.93, 400: 2.46},
        "Temperate": {100: 3.34, 200: 2.70, 400: 2.27},
        "Tropical": {100: 2.79, 200: 2.25, 400: 1.90},
    },
    40: {
        "Arid": {100: 3.21, 200: 2.60, 400: 2.18},
        "Interior": {100: 2.98, 200: 2.41, 400: 2.02},
        "Temperate": {100: 2.75, 200: 2.23, 400: 1.87},
        "Tropical": {100: 2.30, 200: 1.86, 400: 1.56},
    },
    50: {
        "Arid": {100: 2.75, 200: 2.23, 400: 1.89},
        "Interior": {100: 2.56, 200: 2.07, 400: 1.73},
        "Temperate": {100: 2.36, 200: 1.91, 400: 1.60},
        "Tropical": {100: 1.97, 200: 1.59, 400: 1.33},
    },
    65: {
        "Arid": {100: 2.07, 200: 1.75, 400: 1.53},
        "Interior": {100: 1.95, 200: 1.66, 400: 1.46},
        "Temperate": {100: 1.84, 200: 1.59, 400: 1.38},
        "Tropical": {100: 1.61, 200: 1.38, 400: 1.23},
    },
    80: {
        "Arid": {100: 1.56, 200: 1.40, 400: 1.29},
        "Interior": {100: 1.50, 200: 1.36, 400: 1.25},
        "Temperate": {100: 1.45, 200: 1.32, 400: 1.22},
        "Tropical": {100: 1.33, 200: 1.23, 400: 1.14},
    },
    100: {
        "Arid": {100: 1.15, 200: 1.14, 400: 1.11},
        "Interior": {100: 1.15, 200: 1.14, 400: 1.11},
        "Temperate": {100: 1.15, 200: 1.14, 400: 1.11},
        "Tropical": {100: 1.15, 200: 1.14, 400: 1.11},
    },
}


# AS 3600:2018 Table 3.1.7.2 - final design drying shrinkage microstrain.
SHRINKAGE_TABLE = {
    25: {
        "Arid": {50: 810, 100: 720, 200: 590, 400: 470},
        "Interior": {50: 780, 100: 670, 200: 550, 400: 440},
        "Temperate": {50: 740, 100: 630, 200: 520, 400: 410},
        "Tropical": {50: 610, 100: 530, 200: 440, 400: 350},
    },
    32: {
        "Arid": {50: 800, 100: 720, 200: 590, 400: 470},
        "Interior": {50: 770, 100: 670, 200: 560, 400: 440},
        "Temperate": {50: 730, 100: 620, 200: 520, 400: 420},
        "Tropical": {50: 600, 100: 520, 200: 440, 400: 360},
    },
    40: {
        "Arid": {50: 790, 100: 710, 200: 590, 400: 480},
        "Interior": {50: 740, 100: 670, 200: 560, 400: 450},
        "Temperate": {50: 700, 100: 620, 200: 530, 400: 420},
        "Tropical": {50: 580, 100: 500, 200: 440, 400: 360},
    },
    50: {
        "Arid": {50: 780, 100: 700, 200: 590, 400: 490},
        "Interior": {50: 730, 100: 660, 200: 560, 400: 460},
        "Temperate": {50: 690, 100: 620, 200: 530, 400: 440},
        "Tropical": {50: 570, 100: 490, 200: 430, 400: 370},
    },
    65: {
        "Arid": {50: 770, 100: 700, 200: 600, 400: 510},
        "Interior": {50: 730, 100: 650, 200: 570, 400: 490},
        "Temperate": {50: 690, 100: 610, 200: 530, 400: 450},
        "Tropical": {50: 560, 100: 490, 200: 420, 400: 390},
    },
    80: {
        "Arid": {50: 750, 100: 690, 200: 610, 400: 530},
        "Interior": {50: 720, 100: 660, 200: 590, 400: 510},
        "Temperate": {50: 680, 100: 630, 200: 550, 400: 470},
        "Tropical": {50: 560, 100: 520, 200: 470, 400: 390},
    },
    100: {
        "Arid": {50: 740, 100: 690, 200: 620, 400: 560},
        "Interior": {50: 710, 100: 660, 200: 600, 400: 540},
        "Temperate": {50: 680, 100: 640, 200: 580, 400: 520},
        "Tropical": {50: 560, 100: 530, 200: 490, 400: 420},
    },
}


ENV_LABELS = {
    "Arid environment": "Arid",
    "Interior environment": "Interior",
    "Temperate inland environment": "Temperate",
    "Tropical / near-coastal / coastal environment": "Tropical",
}

CREEP_ENV_LABELS = ENV_LABELS
SHRINKAGE_ENV_LABELS = ENV_LABELS


def exposed_perimeter_geometry_values(
    b_mm: float,
    D_mm: float,
    faces_option: str,
) -> dict[str, float]:
    """Gross area, exposed perimeter, and notional thickness for creep/shrinkage."""
    b = float(b_mm or 0.0)
    D = float(D_mm or 0.0)
    faces = str(faces_option or "").replace("â€“", "–").replace("â€œ", "–")
    Ag = b * D
    if faces == "Slab – one face exposed":
        ue = b
    elif faces == "Slab – two faces exposed":
        ue = 2.0 * b
    elif faces == "Beam – three faces exposed":
        ue = b + 2.0 * D
    else:
        ue = 2.0 * (b + D)
    th_raw = 2.0 * Ag / ue if ue > 0 else 0.0
    return {
        "Ag": Ag,
        "ue": ue,
        "th_raw": th_raw,
    }


def creep_closest_fc_row(fc: float) -> int:
    keys = sorted(CREEP_FINAL_TABLE.keys())
    return min(keys, key=lambda key: abs(fc - key))


def creep_closest_th(th: float) -> int:
    options = [100, 200, 400]
    return min(options, key=lambda value: abs(th - value))


def creep_alpha2_from_th(th_mm: float) -> float:
    """Creep time-development alpha2 factor from notional thickness."""
    th = max(float(th_mm or 0.0), 1.0)
    return 1.0 + 1.12 * math.exp(-0.008 * th)


def calc_k2_creep(t_days: float, th_mm: float) -> float:
    """
    k2(t, th) from AS 3600:2018 Fig. 3.1.8.3.
    """
    t = max(t_days, 0.1)
    th = max(th_mm, 1.0)
    alpha2 = creep_alpha2_from_th(th)
    num = alpha2 * (t**0.8)
    den = (t**0.8) + 0.15 * th
    return num / den


def calc_k3(age_at_loading_days: float) -> float:
    """Loading age factor from AS 3600:2018 Cl. 3.1.8.3."""
    tau = max(age_at_loading_days, 1.0)
    return 2.7 / (1.0 + math.log(tau))


def calc_k4(environment_label: str) -> float:
    """Environment factor from AS 3600:2018 Cl. 3.1.8.3."""
    short = ENV_LABELS[environment_label]
    if short == "Arid":
        return 0.70
    if short == "Interior":
        return 0.65
    if short == "Temperate":
        return 0.60
    return 0.50


def calc_k5(fc: float, th_mm: float, k4: float) -> float:
    """High-strength concrete modification factor from AS 3600:2018 Cl. 3.1.8.3."""
    if fc <= 50.0:
        return 1.0

    fc_lim = min(fc, 100.0)
    alpha2 = creep_alpha2_from_th(th_mm)
    alpha3 = 0.7 / (k4 * alpha2)
    return (2.0 - alpha3) - 0.02 * (1.0 - alpha3) * fc_lim


def calc_k6(stress_ratio: float) -> float:
    """Non-linear creep factor from AS 3600:2018 Cl. 3.1.8.3."""
    r = max(stress_ratio, 0.0)
    if r <= 0.45:
        return 1.0
    return math.exp(1.5 * (r - 0.45))


def creep_coefficient_value(
    *,
    k2: float,
    k3: float,
    k4: float,
    k5: float,
    k6: float,
    phi_cc_b: float,
) -> float:
    """Design creep coefficient at time t from AS 3600 factor product."""
    return (
        float(k2 or 0.0)
        * float(k3 or 0.0)
        * float(k4 or 0.0)
        * float(k5 or 0.0)
        * float(k6 or 0.0)
        * float(phi_cc_b or 0.0)
    )


def sustained_creep_stress_mpa(
    *,
    sustained_sigma_cs_mpa: float | None,
    stress_ratio: float,
    fc_mpa: float,
) -> float:
    """Sustained concrete stress used for creep strain."""
    if sustained_sigma_cs_mpa is not None and sustained_sigma_cs_mpa > 0:
        return float(sustained_sigma_cs_mpa)
    return float(stress_ratio or 0.0) * float(fc_mpa or 0.0)


def creep_strain_values(phi_cc_t: float, sigma0_mpa: float, Ec_mpa: float) -> dict[str, float]:
    """Creep strain and microstrain from coefficient, sustained stress, and modulus."""
    Ec = float(Ec_mpa or 0.0)
    eps_cc = float(phi_cc_t or 0.0) * float(sigma0_mpa or 0.0) / Ec if Ec > 0 else 0.0
    return {
        "eps_cc": eps_cc,
        "eps_cc_micro": eps_cc * 1e6,
    }


def basic_creep_coeff(fc: float) -> float:
    """Basic creep coefficient from AS 3600:2018 Table 3.1.8.2."""
    keys = sorted(BASIC_CREEP_COEFF.keys())
    fc_key = min(keys, key=lambda key: abs(fc - key))
    return BASIC_CREEP_COEFF[fc_key]


def final_creep_coeff_table(fc: float, env_label: str, th_table: float) -> float:
    """Final creep coefficient from AS 3600:2018 Table 3.1.8.3."""
    fc_key = creep_closest_fc_row(fc)
    env_key = ENV_LABELS[env_label]
    th_key = creep_closest_th(th_table)
    return CREEP_FINAL_TABLE[fc_key][env_key][th_key]


def shrinkage_closest_fc_row(fc: float) -> int:
    keys = sorted(SHRINKAGE_TABLE.keys())
    return min(keys, key=lambda key: abs(fc - key))


def shrinkage_closest_th(th: float) -> int:
    options = [50, 100, 200, 400]
    return min(options, key=lambda value: abs(th - value))


def shrinkage_eps_final(fc: float, env_label: str, th_table: float) -> float:
    """Return final design drying shrinkage as strain, not microstrain."""
    fc_key = shrinkage_closest_fc_row(fc)
    env_key = ENV_LABELS[env_label]
    th_key = shrinkage_closest_th(th_table)
    microstrain = SHRINKAGE_TABLE[fc_key][env_key][th_key]
    return microstrain * 1e-6


def calc_k1_shrinkage(t_days: float, th_mm: float) -> float:
    """k1(t, th) from AS 3600:2018 Fig. 3.1.7.2."""
    t = max(t_days, 0.1)
    th = max(th_mm, 1.0)
    alpha_t = 0.8 + 1.2 * math.exp(-0.005 * th)
    num = alpha_t * (t**0.8)
    den = (t**0.8) + 0.15 * th
    return num / den


def calc_eps_cse(fc: float, t_days: float) -> float:
    """
    Autogenous shrinkage strain from AS 3600:2018 Cl. 3.1.7.2(2),(3).
    """
    if fc <= 50.0:
        eps_final = (0.07 * fc - 0.5) * 50e-6
    else:
        eps_final = (0.08 * fc - 1.0) * 50e-6

    t = max(t_days, 0.0)
    return eps_final * (1.0 - math.exp(-0.04 * t))


def shrinkage_total_values(k1: float, eps_cse: float, eps_csd_final: float) -> dict[str, float]:
    """Drying, total, and microstrain values for shrinkage result publication."""
    eps_csd_t = float(k1 or 0.0) * float(eps_csd_final or 0.0)
    eps_cs_total = float(eps_cse or 0.0) + eps_csd_t
    return {
        "eps_csd_t": eps_csd_t,
        "eps_cs_total": eps_cs_total,
        "eps_cs_total_micro": eps_cs_total * 1e6,
    }


def autogenous_shrinkage_final_from_current(eps_cse: float, t_days: float) -> float:
    """Back-calculate final autogenous shrinkage for display from current eps_cse."""
    t = float(t_days or 0.0)
    if t <= 0.0:
        return float(eps_cse or 0.0)
    denominator = 1.0 - math.exp(-0.04 * t)
    return float(eps_cse or 0.0) / denominator if denominator != 0.0 else float(eps_cse or 0.0)


# Legacy public names used by the existing pages.
_creep_closest_fc_row = creep_closest_fc_row
_creep_closest_th = creep_closest_th
_shrinkage_closest_fc_row = shrinkage_closest_fc_row
_shrinkage_closest_th = shrinkage_closest_th
_shrinkage_eps_final = shrinkage_eps_final
