"""Read-only glossary and current-value references for every application page.

The page renderers own engineering state and snapshots.  This module only
defines static glossary metadata, projects already-resolved values into an
immutable model, and renders that model in the application sidebar.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import math
import re
from typing import Any


UNAVAILABLE = "—"


@dataclass(frozen=True, slots=True)
class PageReferenceItem:
    """One glossary definition and its already-resolved current value."""

    key: str
    symbol: str
    name: str
    definition: str
    units: str | None
    value: object
    category: str
    display_value: str | None = None
    input_label: str | None = None
    visible: bool = True

    def __post_init__(self) -> None:
        for field_name in ("key", "symbol", "name", "definition", "category"):
            if not str(getattr(self, field_name) or "").strip():
                raise ValueError(f"Page reference {field_name} is required")
        if self.input_label is not None and not str(self.input_label).strip():
            raise ValueError("Page reference input_label cannot be blank")


@dataclass(frozen=True, slots=True)
class PageReferenceModel:
    """Immutable presentation model for one page's sidebar reference."""

    page_key: str
    items: tuple[PageReferenceItem, ...]
    source_label: str | None = None

    def __post_init__(self) -> None:
        keys = [item.key for item in self.items]
        if len(keys) != len(set(keys)):
            raise ValueError(f"Duplicate page reference item key for {self.page_key}")


ReferenceSpec = tuple[str, str, str, str, str | None, str, str | None]


def _spec(
    key: str,
    symbol: str,
    name: str,
    definition: str,
    units: str | None,
    category: str,
    input_label: str | None = None,
) -> ReferenceSpec:
    return (key, symbol, name, definition, units, category, input_label)


_COMMON_GEOMETRY = (
    _spec("sec_shape", "section", "Section shape", "Cross-sectional shape used by the section properties and checks.", None, "Section geometry"),
    _spec("b", "b", "Beam/web width", "Width of the rectangular section or web dimension used by the page.", "mm", "Section geometry"),
    _spec("D", "D", "Overall depth", "Overall section depth measured in the direction of bending or shear.", "mm", "Section geometry"),
    _spec("L", "L", "Beam span", "Reference beam span or effective length.", "mm", "Section geometry"),
    _spec("bf", "b_f", "Flange width", "Width of the compression or tension flange for a flanged section.", "mm", "Section geometry"),
    _spec("tf", "t_f", "Flange thickness", "Thickness of the flange in a T- or I-section.", "mm", "Section geometry"),
    _spec("bf_bot", "b_{f,bot}", "Bottom flange width", "Width of the bottom flange for an I-section.", "mm", "Section geometry"),
    _spec("tf_bot", "t_{f,bot}", "Bottom flange thickness", "Thickness of the bottom flange for an I-section.", "mm", "Section geometry"),
    _spec("bw", "b_w", "Web width", "Width of the web in a T- or I-section.", "mm", "Section geometry"),
    _spec("tw", "t_w", "Web thickness", "Thickness of the web in an I-section.", "mm", "Section geometry"),
    _spec("cover_bot", "c_{bot}", "Bottom cover", "Cover to the bottom longitudinal reinforcement, using the page's existing cover convention.", "mm", "Section geometry"),
    _spec("cover_top", "c_{top}", "Top cover", "Cover to the top longitudinal reinforcement, using the page's existing cover convention.", "mm", "Section geometry"),
    _spec("cover_side", "c_{side}", "Side cover", "Side cover used when resolving longitudinal reinforcement geometry.", "mm", "Section geometry"),
)

_COMMON_MATERIALS = (
    _spec("fc", "f'_{c}", "Concrete compressive strength", "Characteristic 28-day compressive strength of concrete.", "MPa", "Materials"),
    _spec("fsy", "f_{sy}", "Steel yield strength", "Yield strength used for reinforcing steel stress limits.", "MPa", "Materials"),
    _spec("Ec", "E_c", "Concrete elastic modulus", "Concrete elastic modulus used by the page's serviceability or strain calculations.", "MPa", "Materials"),
    _spec("Es", "E_s", "Steel elastic modulus", "Elastic modulus of reinforcing steel.", "MPa", "Materials"),
)

_LONGITUDINAL_REINFORCEMENT = (
    _spec("bot1_layout_mode", "layout_{bot,1}", "Bottom layer 1 layout", "Whether bottom layer 1 is specified by bar count or spacing.", None, "Reinforcement"),
    _spec("bot1_count", "n_{bot,1}", "Bottom layer 1 bar count", "Number of bars in bottom longitudinal reinforcement layer 1.", "bars", "Reinforcement"),
    _spec("db_bot_1", "d_{b,bot,1}", "Bottom layer 1 bar diameter", "Nominal diameter of bottom longitudinal reinforcement layer 1.", "mm", "Reinforcement"),
    _spec("bot1_spacing", "s_{bot,1}", "Bottom layer 1 spacing", "Spacing used when bottom layer 1 is specified by spacing.", "mm", "Reinforcement"),
    _spec("bot2_layout_mode", "layout_{bot,2}", "Bottom layer 2 layout", "Whether bottom layer 2 is specified by bar count or spacing.", None, "Reinforcement"),
    _spec("bot2_count", "n_{bot,2}", "Bottom layer 2 bar count", "Number of bars in bottom longitudinal reinforcement layer 2.", "bars", "Reinforcement"),
    _spec("db_bot_2", "d_{b,bot,2}", "Bottom layer 2 bar diameter", "Nominal diameter of bottom longitudinal reinforcement layer 2.", "mm", "Reinforcement"),
    _spec("bot2_spacing", "s_{bot,2}", "Bottom layer 2 spacing", "Spacing used when bottom layer 2 is specified by spacing.", "mm", "Reinforcement"),
    _spec("rowgap_bot", "g_{bot}", "Bottom row gap", "Vertical gap between bottom longitudinal reinforcement rows.", "mm", "Reinforcement"),
    _spec("top1_layout_mode", "layout_{top,1}", "Top layer 1 layout", "Whether top layer 1 is specified by bar count or spacing.", None, "Reinforcement"),
    _spec("top1_count", "n_{top,1}", "Top layer 1 bar count", "Number of bars in top longitudinal reinforcement layer 1.", "bars", "Reinforcement"),
    _spec("db_top_1", "d_{b,top,1}", "Top layer 1 bar diameter", "Nominal diameter of top longitudinal reinforcement layer 1.", "mm", "Reinforcement"),
    _spec("top1_spacing", "s_{top,1}", "Top layer 1 spacing", "Spacing used when top layer 1 is specified by spacing.", "mm", "Reinforcement"),
    _spec("top2_layout_mode", "layout_{top,2}", "Top layer 2 layout", "Whether top layer 2 is specified by bar count or spacing.", None, "Reinforcement"),
    _spec("top2_count", "n_{top,2}", "Top layer 2 bar count", "Number of bars in top longitudinal reinforcement layer 2.", "bars", "Reinforcement"),
    _spec("db_top_2", "d_{b,top,2}", "Top layer 2 bar diameter", "Nominal diameter of top longitudinal reinforcement layer 2.", "mm", "Reinforcement"),
    _spec("top2_spacing", "s_{top,2}", "Top layer 2 spacing", "Spacing used when top layer 2 is specified by spacing.", "mm", "Reinforcement"),
    _spec("rowgap_top", "g_{top}", "Top row gap", "Vertical gap between top longitudinal reinforcement rows.", "mm", "Reinforcement"),
    _spec("lig_d", "d_{lig}", "Ligature diameter", "Nominal diameter of shear ligatures or stirrups.", "mm", "Reinforcement"),
    _spec("lig_legs", "n_{legs}", "Ligature legs", "Number of effective legs in each shear ligature.", "legs", "Reinforcement"),
    _spec("s_lig", "s_{lig}", "Ligature spacing", "Centre-to-centre spacing of shear ligatures.", "mm", "Reinforcement"),
)

_BENDING_REINFORCEMENT = (
    _spec("nb_or_s_bot_1", "n/s_{bot,1}", "Bottom layer 1 layout", "Bottom layer 1 reinforcement specified by bar count or spacing.", None, "Reinforcement"),
    _spec("db_bot_1", "d_{b,bot,1}", "Bottom layer 1 bar diameter", "Nominal diameter of bottom longitudinal reinforcement layer 1.", "mm", "Reinforcement"),
    _spec("nb_or_s_bot_2", "n/s_{bot,2}", "Bottom layer 2 layout", "Bottom layer 2 reinforcement specified by bar count or spacing.", None, "Reinforcement"),
    _spec("db_bot_2", "d_{b,bot,2}", "Bottom layer 2 bar diameter", "Nominal diameter of bottom longitudinal reinforcement layer 2.", "mm", "Reinforcement"),
    _spec("nb_or_s_top_1", "n/s_{top,1}", "Top layer 1 layout", "Top layer 1 reinforcement specified by bar count or spacing.", None, "Reinforcement"),
    _spec("db_top_1", "d_{b,top,1}", "Top layer 1 bar diameter", "Nominal diameter of top longitudinal reinforcement layer 1.", "mm", "Reinforcement"),
    _spec("nb_or_s_top_2", "n/s_{top,2}", "Top layer 2 layout", "Top layer 2 reinforcement specified by bar count or spacing.", None, "Reinforcement"),
    _spec("db_top_2", "d_{b,top,2}", "Top layer 2 bar diameter", "Nominal diameter of top longitudinal reinforcement layer 2.", "mm", "Reinforcement"),
    _spec("rowgap_bot", "g_{bot}", "Bottom row gap", "Clear vertical gap between bottom reinforcement layers.", "mm", "Reinforcement", "Row gap"),
    _spec("rowgap_top", "g_{top}", "Top row gap", "Clear vertical gap between top reinforcement layers.", "mm", "Reinforcement", "Row gap"),
    _spec("nb_bot", "n_{bot}", "Bottom reinforcement count", "Legacy/resolved bottom reinforcement count used when a single-layer fallback is required.", "bars", "Reinforcement"),
    _spec("db_bot", "d_{b,bot}", "Bottom reinforcement diameter", "Legacy/resolved bottom reinforcement diameter used by fallback geometry.", "mm", "Reinforcement"),
    _spec("nb_top", "n_{top}", "Top reinforcement count", "Legacy/resolved top reinforcement count used when a single-layer fallback is required.", "bars", "Reinforcement"),
    _spec("db_top", "d_{b,top}", "Top reinforcement diameter", "Legacy/resolved top reinforcement diameter used by fallback geometry.", "mm", "Reinforcement"),
    _spec("lig_d", "d_{lig}", "Ligature diameter", "Nominal diameter of shear ligatures associated with the section.", "mm", "Reinforcement"),
    _spec("lig_legs", "n_{legs}", "Ligature legs", "Number of effective ligature legs associated with the section.", "legs", "Reinforcement"),
    _spec("s_lig", "s_{lig}", "Ligature spacing", "Centre-to-centre spacing of shear ligatures associated with the section.", "mm", "Reinforcement"),
)

_COMMON_ACTIONS = (
    _spec("M_star", "M^*", "ULS bending action", "Factored ultimate design bending moment used by the current page.", "kNm", "Design actions"),
    _spec("M_s", "M_s", "SLS bending action", "Service bending moment used for normal-use response.", "kNm", "Design actions"),
    _spec("V_star", "V^*", "ULS shear action", "Factored ultimate design shear action.", "kN", "Design actions"),
    _spec("V_s", "V_s", "SLS shear action", "Service shear action used by the current page where applicable.", "kN", "Design actions"),
    _spec("T_star", "T^*", "Torsion action", "Design torsional action used by shear/torsion checks.", "kNm", "Design actions"),
    _spec("N_star", "N^*", "Axial action", "Design axial action used by the current calculation family.", "kN", "Design actions"),
    _spec("P_star", "P^*", "Prestress action", "Prestress or axial prestressing action used by the current calculation family.", "kN", "Design actions"),
)


PAGE_REFERENCE_BUILDERS: dict[str, Callable[[Mapping[str, Any]], PageReferenceModel]] = {}


def _clean_mapping(values: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(values or {})


def _specs_for_keys(
    specs: tuple[ReferenceSpec, ...],
    keys: set[str] | frozenset[str],
) -> tuple[ReferenceSpec, ...]:
    """Select an ordered subset of metadata without changing its definitions."""

    return tuple(spec for spec in specs if spec[0] in keys)


def _active_section_geometry_specs(
    values: Mapping[str, Any],
    *,
    include_span: bool = True,
    include_covers: bool = False,
    include_side_cover: bool = False,
) -> tuple[ReferenceSpec, ...]:
    """Return only the geometry fields active for the selected section shape."""

    shape = str(values.get("sec_shape") or "RECT").strip().upper()
    if shape not in {"RECT", "T", "I"}:
        shape = "RECT"
    keys = {"sec_shape", "D"}
    if include_span:
        keys.add("L")
    if shape == "RECT":
        keys.add("b")
    elif shape == "T":
        keys.update({"bf", "tf", "bw"})
    else:
        keys.update({"bf", "tf", "tw"})
    if include_covers:
        keys.update({"cover_bot", "cover_top"})
        if include_side_cover:
            keys.add("cover_side")
    return _specs_for_keys(_COMMON_GEOMETRY, keys)


def _source_label(values: Mapping[str, Any], default: str) -> str:
    source = str(values.get("reference_source") or default).strip()
    return source or default


def _display_scalar(value: Any, units: str | None) -> str:
    if value is None:
        return UNAVAILABLE
    if isinstance(value, str):
        return UNAVAILABLE if value.strip().lower() in {"", "none", "nan"} else value
    if isinstance(value, bool):
        return "Included" if value else "Not included"
    if isinstance(value, (list, tuple, set, frozenset)):
        if not value:
            return UNAVAILABLE
        return ", ".join(_display_scalar(item, None) for item in value)
    if isinstance(value, Mapping):
        return "Configured" if value else UNAVAILABLE
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return UNAVAILABLE
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if units is None:
        if number == 0:
            return "0"
        # Dimensionless strains, ratios, and coefficients need more care than
        # a fixed three-decimal display: 0.00142 must not become 0.001.
        text = f"{number:.5g}" if abs(number) < 0.01 else f"{number:,.4g}"
        return text.rstrip("0").rstrip(".") if "." in text else text
    if units in {
        "mm",
        "mm²",
        "mm³",
        "mm⁴",
        "bars",
        "legs",
        "rows",
        "ducts",
        "items",
        "days",
    }:
        precision = 0 if number.is_integer() else 1
    elif units in {"MPa", "kN", "kNm", "kN/m", "m", "°C", "°"}:
        precision = 1 if units not in {"MPa"} else 0
    elif units in {"%", "μɛ"}:
        precision = 1 if units == "%" else 0
    else:
        precision = 3
    text = f"{number:,.{precision}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if units in {"bars", "legs", "rows", "ducts", "items"}:
        count_label = {
            "bars": ("bar", "bars"),
            "legs": ("leg", "legs"),
            "rows": ("row", "rows"),
            "ducts": ("duct", "ducts"),
            "items": ("item", "items"),
        }[units]
        try:
            label = count_label[0] if float(value) == 1 else count_label[1]
        except (TypeError, ValueError):
            label = count_label[1]
        return f"{text} {label}"
    return f"{text} {units}" if units else text


_REPEATING_REINFORCEMENT_LABELS = frozenset(
    {"Rows", "Layout", "Bars", "Spacing", "Ø (mm)", "Row gap"}
)


_COMMON_INPUT_LABELS = {
    "sec_shape": "Section shape",
    "b": "Width b (mm)",
    "D": "Depth D (mm)",
    "L": "Span L (mm)",
    "bf": "Flange width bf (mm)",
    "tf": "Flange thickness tf (mm)",
    "bf_bot": "Bottom flange width bf,bot (mm)",
    "tf_bot": "Bottom flange thickness tf,bot (mm)",
    "bw": "Web width bw (mm)",
    "tw": "Web thickness tw (mm)",
    "cover_bot": "Bottom cover (mm)",
    "cover_top": "Top cover (mm)",
    "cover_side": "Side cover (mm)",
    "side_cover_bot": "Side cover to bottom reinforcement (mm)",
    "side_cover_top": "Side cover to top reinforcement (mm)",
    "fc": "Concrete strength f'c (MPa)",
    "fsy": "Steel yield fsy (MPa)",
    "Ec": "Concrete modulus Ec (MPa)",
    "Es": "Steel modulus Es (MPa)",
    "phi_bend": "Maximum bending strength factor phi_b,max",
    "phi_shear": "Shear strength factor phi_v",
    "phi_torsion": "Torsion strength factor phi_t",
    "actions_source": "Design actions source",
    "actions_mode": "Design actions mode",
    "design_actions_source": "Design actions source",
    "uls_Mstar": "ULS design moment M* (resolved)",
    "uls_Mstar_pos_manual": "Positive design moment Mu*+ (kNm)",
    "uls_Mstar_neg_manual": "Negative design moment Mu*- (kNm)",
    "uls_Vstar": "ULS design shear V* (kN)",
    "uls_Nstar": "ULS axial force N* (kN)",
    "manual_uls_Vstar": "Manual ULS shear V* (kN)",
    "manual_uls_Nstar": "Manual ULS axial force N* (kN)",
    "sls_Mstar": "SLS service moment Ms (resolved)",
    "sls_Mstar_pos_manual": "Positive service moment Ms+ (kNm)",
    "sls_Mstar_neg_manual": "Negative service moment Ms- (kNm)",
    "sls_Vstar": "SLS service shear Vs (kN)",
    "sls_Nstar": "SLS axial force Ns (kN)",
    "manual_sls_Vstar": "Manual SLS shear Vs (kN)",
    "manual_sls_Nstar": "Manual SLS axial force Ns (kN)",
    "Mu_star_manual": "Manual bending moment Mu* (kNm)",
    "Mu_star_pos_manual": "Positive design moment Mu*+ (kNm)",
    "Mu_star_neg_manual": "Negative design moment Mu*- (kNm)",
    "Tu_star": "Torsion action T* (kNm)",
    "P_star": "Prestress force P* (kN)",
    "N_star": "Axial force N* (kN)",
    "lig_d": "Link Ø (mm)",
    "lig_legs": "No. of legs",
    "s_lig": "Provided link spacing (mm)",
    "n_ducts": "Number of ducts crossing web",
    "duct_dia": "Duct diameter (mm)",
    "d_g": "Maximum aggregate size d_g (mm)",
    "k_d_option": "k_d factor for prestressing ducts",
    "k_v_method": "k_v method",
    "exposure_class": "Exposure class",
    "wmax_char_limit": "Crack-width limit wmax (mm)",
    "crack_member_type": "Resultant action",
    "crack_k1": "k₁ (bond coefficient)",
    "crack_k2": "k2 (strain distribution factor)",
    "crack_control_method": "Calculation method",
    "member_faces_exposed": "Member / faces exposed",
    "shrinkage_env": "Shrinkage environment (Table 3.1.7.2)",
    "shrinkage_method": "Calculation method",
    "shrinkage_relative_humidity_percent": "Relative humidity (%)",
    "shrinkage_cement_class": "Cement class",
    "shrinkage_drying_start_age_days": "End of curing / start of drying (days)",
    "env_option": "Creep environment (Tables 3.1.8.2 & 3.1.8.3)",
    "t_creep": "Time after loading t (days)",
    "age_at_loading": "Age at loading τ (days)",
    "t_shrink": "Shrinkage time t (days)",
    "defl_support_type": "Support condition (k₂)",
    "defl_limit_ratio": "Deflection limit L/Δ",
    "defl_use_simplified_ief": "Use simplified reinforced-member Iₑf (AS 3600 Cl. 8.5.3.1(2),(3))",
    "defl_Ief_user": "User-specified Iₑf (mm⁴)",
    "crack_theta_deg": "Reference crack angle θ (°)",
    "crack_c766_restraint_type": "Restraint type",
    "crack_c766_t1_c": "Early temperature drop T1 / ΔT (°C)",
    "crack_c766_t2_c": "Long-term temperature change T2 (°C)",
    "crack_c766_alpha_micro_per_c": "Thermal expansion (µε/°C)",
    "crack_c766_restraint_early": "Early restraint R1",
    "crack_c766_restraint_medium": "Medium-term restraint R2",
    "crack_c766_restraint_long": "Long-term restraint R3",
    "crack_c766_tensile_capacity_micro": "Tensile strain capacity (µε)",
    "crack_c766_effective_reinforcement_ratio": "Effective reinforcement ratio",
    "crack_c766_modular_ratio": "Effective modular ratio αe",
    "crack_c766_non_uniform_k": "Non-uniform stress coefficient k",
    "crack_c766_stress_distribution_kc": "Stress-distribution coefficient kc",
    "crack_c766_characteristic_tensile_mpa": "Characteristic tensile strength at cracking (MPa)",
    "crack_c766_total_reinforcement_ratio": "Total reinforcement / tension-area ratio",
    "crack_c766_bar_diameter_mm": "Bar diameter (mm)",
    "crack_c766_cover_mm": "Cover (mm)",
    "crack_wall_thickness_mm": "Wall thickness (mm)",
    "crack_wall_horizontal_area_per_face": "Provided horizontal area per face (mm²/m)",
    "crack_wall_vertical_spacing_mm": "Provided vertical spacing (mm)",
    "crack_wall_in_base_zone": "Base zone (height equal to wall thickness)",
}


_PAGE_INPUT_LABEL_OVERRIDES: dict[str, dict[str, str]] = {
    "inputs": {
        "b": "Width b (mm)",
        "D": "Depth D (mm)",
        "L": "Span L (mm)",
        "sec_shape": "Section shape",
        "bw": "Web width bw (mm)",
        "tw": "Web thickness tw (mm)",
        "bf_bot": "Bottom flange width bf,bot (mm)",
        "tf_bot": "Bottom flange thickness tf,bot (mm)",
        "cover_bot": "Bottom cover (mm)",
        "cover_top": "Top cover (mm)",
        "cover_side": "Side cover (mm)",
        "side_cover_bot": "Side cover to bottom reinforcement (mm)",
        "side_cover_top": "Side cover to top reinforcement (mm)",
        "fc": "Concrete MPa",
        "fsy": "Steel MPa",
        "Tu_star": "Design torsion Tu* (kNm)",
        "P_star": "Applied prestress P* (kN)",
        "uls_Mstar_pos_manual": "Positive design moment Mu*+ (kNm)",
        "uls_Mstar_neg_manual": "Negative design moment Mu*- (kNm)",
        "sls_Mstar_pos_manual": "Positive design moment Mu*+ (kNm)",
        "sls_Mstar_neg_manual": "Negative design moment Mu*- (kNm)",
        "uls_Vstar": "Design shear Vu* (kN)",
        "sls_Vstar": "Design shear Vu* (kN)",
        "manual_uls_Vstar": "Design shear Vu* (kN)",
        "manual_sls_Vstar": "Design shear Vu* (kN)",
        "uls_Nstar": "Axial force N* (kN)",
        "sls_Nstar": "Axial force N* (kN)",
        "manual_uls_Nstar": "Axial force N* (kN)",
        "manual_sls_Nstar": "Axial force N* (kN)",
        "inputs_action_source_toggle": "Use Load Analysis actions for Beam Inputs",
        "actions_source": "Use Load Analysis actions for Beam Inputs",
        "inputs_loads_edit_toggle": "View SLS loads",
        "inputs_detailed_mode_toggle": "Design mode",
        "inputs_detailed_mode": "Design mode",
        "phi_bend": "Maximum bending strength factor phi_b,max",
        "defl_limit_ratio": "Deflection limit L/Δ",
        "defl_support_type": "Support condition (k₂)",
        "design_optimisation_goal": "Optimise for",
        "optimisation_lock_geometry": "Lock geometry",
        "member_faces_exposed": "Member / faces exposed",
        "shrinkage_env": "Shrinkage environment (Table 3.1.7.2)",
        "env_option": "Creep environment (Tables 3.1.8.2 & 3.1.8.3)",
        "t_creep": "Creep time t (days)",
        "d_g": "Maximum aggregate size d_g (mm)",
        "k_v_method": "k_v method",
        "exposure_class": "Exposure class",
        "crack_member_type": "Resultant action",
        "crack_k1": "k1",
        "crack_k2": "k₂ (strain distribution factor)",
        "lig_d": "Link dia (mm)",
        "lig_legs": "No. of legs",
        "s_lig": "Link spacing (mm)",
        "n_ducts": "Number of ducts crossing web",
        "duct_dia": "Duct diameter (mm)",
        "inputs_top_flange_reo_enabled": "Enable top flange bars",
        "inputs_bot_flange_reo_enabled": "Enable bottom flange bars",
        "top_flange_reo_enabled": "Enable top flange bars",
        "bot_flange_reo_enabled": "Enable bottom flange bars",
        "top_flange_mirror_lr": "Mirror top left/right",
        "bot_flange_mirror_lr": "Mirror bottom left/right",
        "top_flange_left_count": "Top flange left bars",
        "top_flange_left_dia": "Top flange left dia (mm)",
        "top_flange_left_rows": "Top flange left rows",
        "top_flange_left_row_spacing": "Top flange left row spacing (mm)",
        "top_flange_left_clear_spacing_mode": "Top flange left clear spacing mode",
        "top_flange_right_count": "Top flange right bars",
        "top_flange_right_dia": "Top flange right dia (mm)",
        "top_flange_right_rows": "Top flange right rows",
        "top_flange_right_row_spacing": "Top flange right row spacing (mm)",
        "top_flange_right_clear_spacing_mode": "Top flange right clear spacing mode",
        "bot_flange_left_count": "Bottom flange left bars",
        "bot_flange_left_dia": "Bottom flange left dia (mm)",
        "bot_flange_left_rows": "Bottom flange left rows",
        "bot_flange_left_row_spacing": "Bottom flange left row spacing (mm)",
        "bot_flange_left_clear_spacing_mode": "Bottom flange left clear spacing mode",
        "bot_flange_right_count": "Bottom flange right bars",
        "bot_flange_right_dia": "Bottom flange right dia (mm)",
        "bot_flange_right_rows": "Bottom flange right rows",
        "bot_flange_right_row_spacing": "Bottom flange right row spacing (mm)",
        "bot_flange_right_clear_spacing_mode": "Bottom flange right clear spacing mode",
        "top_flange_transverse_enabled": "Enable top flange transverse",
        "bot_flange_transverse_enabled": "Enable bottom flange transverse",
        "top_flange_transverse_dia": "Top flange transverse dia (mm)",
        "bot_flange_transverse_dia": "Bottom flange transverse dia (mm)",
        "top_flange_transverse_spacing": "Top flange transverse spacing (mm)",
        "bot_flange_transverse_spacing": "Bottom flange transverse spacing (mm)",
        "top_flange_transverse_legs": "Top flange transverse legs",
        "bot_flange_transverse_legs": "Bottom flange transverse legs",
    },
    "bending": {
        "fc": "Concrete strength f'c (MPa)",
        "fsy": "Steel yield fsy (MPa)",
        "M_star": "Current ULS moment M* (kNm)",
        "M_s": "Current SLS moment Ms (kNm)",
        "N_star": "Resolved axial force N* used by bending (kN)",
        "P_star": "Prestress force P* (kN)",
        "uls_Mstar_pos_manual": "Positive design moment Mu*+ (kNm)",
        "uls_Mstar_neg_manual": "Negative design moment Mu*- (kNm)",
        # The Bending editor keeps the established Mu* labels while the
        # View SLS loads switch selects the SLS value behind those controls.
        "sls_Mstar_pos_manual": "Positive design moment Mu*+ (kNm)",
        "sls_Mstar_neg_manual": "Negative design moment Mu*- (kNm)",
        "sls_ignore_compression_reinforcement": "Ignore compression reinforcement",
        "concrete_stress_model": "Use parabolic (non-linear) stress block",
        "loads_edit_mode": "View SLS loads",
    },
    "shear": {
        "fc": "Concrete strength f'c (MPa)",
        "fsy": "Steel yield f_sy (MPa)",
        "V_star": "Resolved design shear V* (kN)",
        "M_star": "Resolved design moment M* (kNm)",
        "T_star": "Resolved torsion T* (kNm)",
        "N_star": "Resolved axial force N* (kN, +tension)",
        "P_v": "Prestress force P* (kN)",
        "n_ducts": "Number of ducts crossing web",
        "duct_dia": "Duct diameter (mm)",
        "shear_include_prestress_effects_ui": "Include prestress effects",
        "loads_edit_mode": "View SLS loads",
        "defl_support_type": "Support condition (k₂)",
        "s_lig": "Provided link spacing (mm)",
        "phi_shear": "φ – strength reduction for shear",
        "P_star": "Prestress force P* (kN)",
        "uls_Mstar_pos_manual": "Positive design moment Mu*+ (kNm)",
        "uls_Mstar_neg_manual": "Negative design moment Mu*- (kNm)",
        "sls_Mstar_pos_manual": "Positive design moment Mu*+ (kNm)",
        "sls_Mstar_neg_manual": "Negative design moment Mu*- (kNm)",
        "manual_uls_Vstar": "Design shear V* (kN)",
        "manual_sls_Vstar": "Design shear V* (kN)",
        "manual_uls_Nstar": "Axial force N* (kN, +tension)",
        "manual_sls_Nstar": "Axial force N* (kN, +tension)",
    },
    "design": {
        "actions_source": "Use Load Analysis actions for Beam Inputs",
        "load_case": "Loading condition",
        "support_condition": "Support condition",
        "L_m": "Span L (m)",
        "design_beam_system_mode": "Beam system mode",
        "design_support_condition": "Support condition",
        "span_L_m": "Span L (m)",
        "g_udl_kNm_per_m": "Dead UDL g (kN/m)",
        "q_udl_kNm_per_m": "Live UDL q (kN/m)",
        "psi_udl": "Sustained factor ψ_s",
        "G_point_kN": "Dead point load G (kN)",
        "Q_point_kN": "Live point load Q (kN)",
        "psi_point": "Sustained factor ψ_s for point load",
        "a_m": "Point-load distance a (m)",
        "a_udl_m": "UDL length a from left (m)",
        "a_cant_m": "Cantilever load location a (m)",
        "a_overhang_m": "Overhang length (m)",
        "design_actions_source": "Design actions source",
        "active_mode": "Diagram/action state: SLS",
    },
    "creep": {
        "b": "Section width b (mm)",
        "D": "Overall depth D (mm)",
        "fc": "Concrete strength f'c (MPa)",
        "Ec": "Concrete modulus Ec (MPa)",
        "member_faces_exposed": "Member / faces exposed",
        "env_option": "Creep environment (Tables 3.1.8.2 & 3.1.8.3)",
        "t_creep": "Time after loading t (days)",
        "age_at_loading": "Age at loading τ (days)",
    },
    "shrinkage": {
        "b": "Section width b (mm)",
        "D": "Overall depth D (mm)",
        "fc": "Concrete strength f'c (MPa)",
        "member_faces_exposed": "Member / faces exposed",
        "shrinkage_env": "Shrinkage environment (Table 3.1.7.2)",
        "shrinkage_method": "Calculation method",
        "t_shrink": "Time since commencement of drying t (days)",
        "shrinkage_relative_humidity_percent": "Relative humidity (%)",
        "shrinkage_cement_class": "Cement class",
        "shrinkage_drying_start_age_days": "End of curing / start of drying (days)",
    },
    "crack": {
        "b": "Section width b (mm)",
        "D": "Overall depth D (mm)",
        "fc": "Concrete strength f'c (MPa)",
        "cover_mm": "Clear cover to tensile bars c (mm)",
        "crack_member_type": "Resultant action",
        "crack_k1": "k₁ (bond coefficient)",
        "crack_k2": "k₂ (strain distribution factor)",
        "wmax_char_limit": "Characteristic crack-width limit w′max (mm)",
        "bar_diameter_mm": "Tensile bar diameter (mm)",
        "bar_spacing_mm": "Tensile bar spacing (mm)",
    },
    "deflection": {
        "b": "Beam width b (mm)",
        "D": "Beam depth D (mm)",
        "L": "Span L (mm)",
        "fc": "Concrete strength f'c (MPa)",
        "defl_support_type": "Support condition (k₂)",
        "defl_limit_ratio": "Deflection limit L/Δ",
        "span_L_m": "Analysis span L (m)",
        "defl_use_simplified_ief": "Use simplified reinforced-member Iₑf (AS 3600 Cl. 8.5.3.1(2),(3))",
        "defl_Ief_user": "User-specified Iₑf (mm⁴)",
        "g_udl_kNm_per_m": "Dead UDL g (kN/m)",
        "q_udl_kNm_per_m": "Live UDL q (kN/m)",
        "psi_udl": "Sustained factor ψ_s",
        "G_point_kN": "Dead point load G (kN)",
        "Q_point_kN": "Live point load Q (kN)",
        "psi_point": "Sustained factor ψ_s for point load",
    },
}


def _page_input_label(
    page_key: str,
    key: str,
    fallback: str,
    values: Mapping[str, Any],
) -> str:
    """Return the label a user sees beside the corresponding page input."""

    page_overrides = _PAGE_INPUT_LABEL_OVERRIDES.get(page_key, {})
    if key in page_overrides:
        return page_overrides[key]
    if page_key == "design" and key == "load_psi_udl":
        is_multi_span = str(values.get("beam_system_mode") or "").lower() == "multi-span"
        return "Sustained factor ψ_s for UDL" if is_multi_span else "Sustained factor ψ_s"
    if key in _COMMON_INPUT_LABELS:
        label = _COMMON_INPUT_LABELS[key]
        if key == "bf" and str(values.get("sec_shape") or "").upper() == "I":
            return "Top flange width bf (mm)"
        if key == "tf" and str(values.get("sec_shape") or "").upper() == "I":
            return "Top flange thickness tf (mm)"
        return label

    row_match = re.match(r"^(bot|top)_row_(\d+)_(count|mode|bars|spacing|dia)$", key)
    if row_match:
        face, row, field = row_match.groups()
        face_label = "Bottom Reinforcement" if face == "bot" else "Top Reinforcement"
        field_label = {
            "count": "Rows",
            "mode": "Layout",
            "bars": "Bars",
            "spacing": "Spacing",
            "dia": "Ø (mm)",
        }[field]
        return field_label

    if key in {"bot_row_count", "top_row_count"}:
        return "Rows"

    legacy_row = re.match(r"^(bot|top)([1-4])_(layout_mode|count|spacing)$", key)
    if legacy_row:
        face, row, field = legacy_row.groups()
        face_label = "Bottom Reinforcement" if face == "bot" else "Top Reinforcement"
        field_label = {
            "layout_mode": "Layout",
            "count": "Bars",
            "spacing": "Spacing",
        }[field]
        return f"{face_label} — Layer {row} — {field_label}"

    canonical_reo_match = re.match(r"^(nb_or_s|db)_(bot|top)(?:_(\d+))?$", key)
    if canonical_reo_match:
        field, face, row = canonical_reo_match.groups()
        face_label = "Bottom Reinforcement" if face == "bot" else "Top Reinforcement"
        row_label = f" — Layer {row}" if row and not (field == "nb_or_s" and row == "1") else ""
        if field == "nb_or_s":
            return face_label if row == "1" else f"{face_label}{row_label} — Layout"
        return f"{face_label}{row_label} — Ø (mm)"

    if key in {"rowgap_bot", "rowgap_top"}:
        return "Row gap"

    if key in {"nb_bot", "nb_top"}:
        face_label = "Bottom Reinforcement" if key.endswith("bot") else "Top Reinforcement"
        return f"{face_label} — Resolved bar count"

    flange_match = re.match(
        r"^(top|bot)_flange_(left|right|transverse)_(.+)$", key
    )
    if flange_match:
        face, side, field = flange_match.groups()
        face_label = "Top" if face == "top" else "Bottom"
        side_label = side.replace("_", " ").title()
        field_label = {
            "enabled": "Enable",
            "mirror_lr": "Mirror left/right",
            "count": "bars",
            "dia": "dia (mm)",
            "rows": "rows",
            "row_spacing": "row spacing (mm)",
            "clear_spacing_mode": "clear spacing mode",
            "spacing": "spacing (mm)",
            "legs": "legs",
        }.get(field, field.replace("_", " "))
        if side == "transverse":
            return f"{face} flange transverse {field_label}"
        return f"{face_label} flange {side_label} {field_label}"

    load_row = re.match(r"^(design_ms|load_ms)_(G|Q|g|q)_(\d+)$", key)
    if load_row:
        _, load_type, row = load_row.groups()
        prefix = "Point" if load_type.isupper() else "UDL"
        name = "dead" if load_type.lower() == "g" else "live"
        unit = "kN" if load_type.isupper() else "kN/m"
        return (
            f"{prefix} {row}: {name} load {load_type}_{row} ({unit})"
            if prefix == "Point"
            else f"{prefix} {row}: {name} {load_type}_{row} ({unit})"
        )

    load_position = re.match(r"^(design_ms|load_ms)_(x0|x1|x)_(\d+)$", key)
    if load_position:
        _, position, row = load_position.groups()
        position_label = {"x0": "start x_start", "x1": "end x_end", "x": "position x"}[position]
        return f"{('UDL' if position in {'x0', 'x1'} else 'Point')} {row}: {position_label}_{row} (m)"

    point_load = re.match(r"^design_point_(G|Q|x)_(\d+)$", key)
    if point_load:
        load_type, row = point_load.groups()
        if load_type == "x":
            return f"Point {row}: position x_{row} (m)"
        return f"Point {row}: {'dead' if load_type == 'G' else 'live'} load {load_type}_{row} (kN)"

    span_length = re.match(r"^(?:design_span_len|sfd_span_len)_(\d+)$", key)
    if span_length:
        return f"Span {span_length.group(1)} length (m)"

    load_point = re.match(r"^load_(G|Q|x)_point(?:_(\d+))?$", key)
    if load_point:
        load_type, row = load_point.groups()
        if load_type == "x":
            return (
                f"Position x_{row} (m)" if row else "Distance a from left support (m)"
            )
        if row:
            return f"{'Dead' if load_type == 'G' else 'Live'} point load {load_type}_{row} (kN)"
        return f"{'Dead' if load_type == 'G' else 'Live'} point load {load_type} (kN)"

    if key in {
        "load_g_udl", "load_q_udl", "load_psi_udl", "load_psi_point",
        "sfd_a_udl", "sfd_a_cant", "sfd_a_overhang", "sfd_L_m",
        "sfd_span_count", "sfd_ms_point_count", "sfd_ms_udl_count",
        "sfd_case", "sfd_support_condition", "sfd_beam_system_mode",
        "sfd_bmd_show_m_peak_marker", "sfd_support_type_1", "sfd_support_type_2",
        "sfd_support_type_3", "sfd_support_type_4", "sfd_support_type_5",
        "sfd_support_type_6",
    }:
        return {
            "load_g_udl": "Dead UDL g (kN/m)",
            "load_q_udl": "Live UDL q (kN/m)",
            "load_psi_udl": "Sustained factor ψ_s",
            "load_psi_point": "Sustained factor ψ_s for point load",
            "sfd_a_udl": "UDL length a from left (m)",
            "sfd_a_cant": "Distance a from fixed end (m)",
            "sfd_a_overhang": "Overhang length a (m)",
            "sfd_L_m": "Span L (m)",
            "sfd_span_count": "Number of spans",
            "sfd_ms_point_count": "Number of point loads",
            "sfd_ms_udl_count": "Number of UDL segments",
            "sfd_case": "Loading condition",
            "sfd_support_condition": "Support condition",
            "sfd_beam_system_mode": "Beam system mode",
            "sfd_bmd_show_m_peak_marker": "Show M peak marker",
            "sfd_support_type_1": "Support 1",
            "sfd_support_type_2": "Support 2",
            "sfd_support_type_3": "Support 3",
            "sfd_support_type_4": "Support 4",
            "sfd_support_type_5": "Support 5",
            "sfd_support_type_6": "Support 6",
        }[key]

    support = re.match(r"^(?:design_support_type|sfd_support_type)_(\d+)$", key)
    if support:
        return f"Support {support.group(1)}"

    pretty = fallback
    return pretty


def _reinforcement_display_values(values: Mapping[str, Any]) -> dict[str, str]:
    """Project the authoritative row model into the page's reo notation."""

    from application.bottom_reinforcement_policy import (
        format_longitudinal_reinforcement_rows,
    )

    source = dict(values)
    def _summary(face: str) -> str:
        try:
            row_count = int(float(source.get(f"{face}_row_count", 1) or 0))
        except (TypeError, ValueError):
            row_count = 1
        if row_count <= 0:
            return "None"
        if row_count <= 2:
            return format_longitudinal_reinforcement_rows(source, face=face)
        parts: list[str] = []
        for row in range(1, min(4, row_count) + 1):
            mode = str(source.get(f"{face}_row_{row}_mode", "Count") or "Count").strip().lower()
            try:
                diameter = int(float(source.get(f"{face}_row_{row}_dia", 0) or 0))
                if mode == "spacing":
                    spacing = int(float(source.get(f"{face}_row_{row}_spacing", 0) or 0))
                    if diameter > 0 and spacing > 0:
                        parts.append(f"N{diameter} @ {spacing}")
                else:
                    bars = int(float(source.get(f"{face}_row_{row}_bars", 0) or 0))
                    if diameter > 0 and bars > 0:
                        parts.append(f"{bars}-N{diameter}")
            except (TypeError, ValueError):
                continue
        return " + ".join(parts) if parts else "None"

    display_values = {
        "nb_or_s_bot_1": _summary("bot"),
        "nb_or_s_top_1": _summary("top"),
        # Keep the compact reo notation as an explicitly derived, read-only
        # summary.  The row controls remain the only engineering inputs.
        "bot_reinforcement_notation": _summary("bot"),
        "top_reinforcement_notation": _summary("top"),
    }
    for face in ("bot", "top"):
        face_name = "Bottom" if face == "bot" else "Top"
        for row in range(1, 5):
            mode = str(
                source.get(
                    f"{face}_row_{row}_mode",
                    source.get(f"{face}{row}_layout_mode", "Count"),
                )
                or "Count"
            ).strip().lower()
            count = source.get(
                f"{face}_row_{row}_bars",
                source.get(f"{face}{row}_count", source.get(f"nb_or_s_{face}_{row}")),
            )
            spacing = source.get(
                f"{face}_row_{row}_spacing",
                source.get(f"{face}{row}_spacing"),
            )
            diameter = source.get(
                f"{face}_row_{row}_dia",
                source.get(f"db_{face}_{row}", source.get(f"db_{face}")),
            )
            try:
                diameter_text = f"N{int(float(diameter or 0))}"
                if mode == "spacing":
                    row_text = (
                        f"{diameter_text} @ {int(float(spacing or 0))}"
                        if float(spacing or 0) > 0 and float(diameter or 0) > 0
                        else UNAVAILABLE
                    )
                else:
                    row_text = (
                        f"{int(float(count or 0))}-{diameter_text}"
                        if float(count or 0) > 0 and float(diameter or 0) > 0
                        else UNAVAILABLE
                    )
            except (TypeError, ValueError):
                row_text = UNAVAILABLE
            display_values[f"nb_or_s_{face}_{row}"] = (
                row_text if row == 2 else display_values[f"nb_or_s_{face}_1"]
            )
    return display_values


def _active_reinforcement_notation_specs(
    *,
    faces: tuple[str, ...] = ("bot", "top"),
) -> tuple[ReferenceSpec, ...]:
    """Describe compact read-only reo notation for the active row controls."""

    specs: list[ReferenceSpec] = []
    for face in faces:
        face_name = "Bottom" if face == "bot" else "Top"
        specs.append(
            _spec(
                f"{face}_reinforcement_notation",
                f"reo_{{{face}}}",
                f"{face_name} reinforcement arrangement",
                "Compact read-only notation derived from the active Rows, Layout, Bars/Spacing and Ø (mm) inputs; it is not a second input or calculation source.",
                None,
                "Reinforcement",
                "Read-only reo summary",
            )
        )
    return tuple(specs)


def _with_row_model_aliases(values: Mapping[str, Any]) -> dict[str, Any]:
    """Expose the current row-widget values without changing their owner."""

    source = dict(values)
    for face in ("bot", "top"):
        second_layout = source.get(f"nb_or_s_{face}_2")
        second_count = source.get(f"{face}_row_2_bars", source.get(f"{face}2_count", 0))
        if f"{face}_row_count" not in source:
            try:
                source[f"{face}_row_count"] = 2 if (
                    isinstance(second_layout, (int, float))
                    and float(second_layout or 0) > 0
                ) or float(second_count or 0) > 0 else 1
            except (TypeError, ValueError):
                source[f"{face}_row_count"] = 1
        for row in range(1, 5):
            legacy_layout = source.get(f"nb_or_s_{face}_{row}")
            layout_mode = source.get(
                f"{face}{row}_layout_mode",
                "Spacing" if isinstance(legacy_layout, (int, float)) and float(legacy_layout) >= 30 else "Count",
            )
            source.setdefault(f"{face}_row_{row}_mode", layout_mode)
            source.setdefault(
                f"{face}_row_{row}_bars",
                source.get(f"{face}{row}_count", legacy_layout if layout_mode == "Count" else 0),
            )
            source.setdefault(
                f"{face}_row_{row}_spacing",
                source.get(f"{face}{row}_spacing", legacy_layout if layout_mode == "Spacing" else 0),
            )
            source.setdefault(
                f"{face}_row_{row}_dia",
                source.get(f"db_{face}_{row}", source.get(f"db_{face}", 0)),
            )
    return source


def _active_longitudinal_row_specs(
    values: Mapping[str, Any],
    *,
    faces: tuple[str, ...] = ("bot", "top"),
) -> tuple[ReferenceSpec, ...]:
    """Build metadata for the row controls currently visible on a page."""

    source = _with_row_model_aliases(values)
    specs: list[ReferenceSpec] = []
    for face in faces:
        face_name = "Bottom Reinforcement" if face == "bot" else "Top Reinforcement"
        try:
            row_count = max(0, min(4, int(float(source.get(f"{face}_row_count", 1) or 0))))
        except (TypeError, ValueError):
            row_count = 1
        specs.append(
            _spec(
                f"{face}_row_count",
                f"n_{{{face},rows}}",
                f"{face_name} — Rows",
                f"Number of active {face_name.lower()} layers shown in the page editor.",
                "rows",
                "Reinforcement",
                "Rows",
            )
        )
        for row in range(1, row_count + 1):
            mode = str(source.get(f"{face}_row_{row}_mode", "Count") or "Count").strip().lower()
            specs.append(
                _spec(
                    f"{face}_row_{row}_mode",
                    f"layout_{{{face},{row}}}",
                    f"{face_name} — Layer {row} — Layout",
                    f"Select Count or Spacing for {face_name.lower()} layer {row}.",
                    None,
                    "Reinforcement",
                    "Layout",
                )
            )
            if mode == "spacing":
                specs.append(
                    _spec(
                        f"{face}_row_{row}_spacing",
                        f"s_{{{face},{row}}}",
                        f"{face_name} — Layer {row} — Spacing",
                        f"Centre-to-centre spacing of {face_name.lower()} layer {row}.",
                        "mm",
                        "Reinforcement",
                        "Spacing",
                    )
                )
            else:
                specs.append(
                    _spec(
                        f"{face}_row_{row}_bars",
                        f"n_{{{face},{row}}}",
                        f"{face_name} — Layer {row} — Bars",
                        f"Number of bars in {face_name.lower()} layer {row}.",
                        "bars",
                        "Reinforcement",
                        "Bars",
                    )
                )
            specs.append(
                _spec(
                    f"{face}_row_{row}_dia",
                    f"d_{{b,{face},{row}}}",
                    f"{face_name} — Layer {row} — Ø (mm)",
                    f"Nominal diameter of {face_name.lower()} layer {row} bars.",
                    "mm",
                    "Reinforcement",
                    "Ø (mm)",
                )
            )
    return tuple(specs)


def _items(
    values: Mapping[str, Any],
    specs: tuple[ReferenceSpec, ...],
    *,
    page_key: str,
    display_values: Mapping[str, str] | None = None,
    hidden_keys: set[str] | frozenset[str] = frozenset(),
) -> tuple[PageReferenceItem, ...]:
    display_values = display_values or {}
    return tuple(
        PageReferenceItem(
            key=key,
            symbol=symbol,
            name=name,
            definition=definition,
            units=units,
            value=values.get(key),
            category=category,
            display_value=display_values.get(key),
            # Page adapters own the exact label for a shared key.  This must
            # take precedence over a family-level label because the same
            # canonical value is presented differently on Inputs, Bending and
            # Shear (for example Vu* versus V*).
            input_label=(
                _page_input_label(page_key, key, name, values)
                if key in _PAGE_INPUT_LABEL_OVERRIDES.get(page_key, {})
                else input_label or _page_input_label(page_key, key, name, values)
            ),
            visible=key not in hidden_keys,
        )
        for key, symbol, name, definition, units, category, input_label in specs
    )


def _model(
    page_key: str,
    values: Mapping[str, Any],
    specs: tuple[ReferenceSpec, ...],
    *,
    source_label: str | None = None,
    display_values: Mapping[str, str] | None = None,
    hidden_keys: set[str] | frozenset[str] = frozenset(),
) -> PageReferenceModel:
    return PageReferenceModel(
        page_key=page_key,
        items=_items(
            values,
            specs,
            page_key=page_key,
            display_values=display_values,
            hidden_keys=hidden_keys,
        ),
        source_label=source_label,
    )


def _parameter_spec(key: str) -> ReferenceSpec:
    """Provide stable metadata for canonical Beam Inputs parameters.

    The canonical parameter list is maintained by the Inputs state contract;
    this adapter keeps the sidebar coverage in lockstep with that list while
    preserving engineer-friendly terminology for the common calculation
    fields and the repeating reinforcement/load rows.
    """

    # The Inputs contract spans several calculation families.  Reuse the
    # family glossary metadata where the same canonical key already has a
    # precise definition rather than inventing a second description here.
    known: dict[str, ReferenceSpec] = {}
    for group_name in (
        "_COMMON_GEOMETRY",
        "_COMMON_MATERIALS",
        "_LONGITUDINAL_REINFORCEMENT",
        "_COMMON_ACTIONS",
        "_BENDING_SPECS",
        "_SHEAR_SPECS",
        "_CREEP_SPECS",
        "_SHRINKAGE_SPECS",
        "_CRACK_SPECS",
        "_DEFLECTION_SPECS",
    ):
        for item in globals().get(group_name, ()):
            # Keep the first, shared definition for keys that are reused by
            # several calculation families.  A later family-specific alias
            # must not silently replace the meaning of an Inputs-page value.
            known.setdefault(item[0], item)
    if key == "actions_source":
        return _spec(
            key,
            "source",
            "Design actions source",
            "Whether Beam Inputs uses its manual action inputs or the resolved Load Analysis actions.",
            None,
            "Method / assumptions",
            "Use Load Analysis actions for Beam Inputs",
        )
    if key in known and key not in {"P_star", "N_star", "Tu_star"}:
        if key in {"rowgap_bot", "rowgap_top"}:
            face_name = "Bottom Reinforcement" if key.endswith("bot") else "Top Reinforcement"
            return _spec(
                key,
                f"g_{{{key[-3:]}}}",
                f"{face_name} — Row gap",
                f"Clear vertical gap between {face_name.lower()} rows.",
                "mm",
                "Reinforcement",
                "Row gap",
            )
        return known[key]

    if key in {"bot_row_count", "top_row_count"}:
        face = "bot" if key.startswith("bot") else "top"
        face_name = "Bottom Reinforcement" if face == "bot" else "Top Reinforcement"
        return _spec(
            key,
            f"n_{{{face},rows}}",
            f"{face_name} — Rows",
            f"Number of active {face_name.lower()} layers shown in the page editor.",
            "rows",
            "Reinforcement",
            "Rows",
        )

    canonical_metadata = {
        "Tu_star": _spec(
            key,
            "T^*",
            "Design torsion",
            "Design torsional action entered for the Beam Inputs page.",
            "kNm",
            "Design actions",
        ),
        "P_star": _spec(
            key,
            "P^*",
            "Applied prestress",
            "Prestress force entered for the active Beam Inputs action set.",
            "kN",
            "Design actions",
        ),
        "N_star": _spec(
            key,
            "N^*",
            "Axial action",
            "Axial force entered for the active Beam Inputs action set.",
            "kN",
            "Design actions",
        ),
        "L_m": _spec(
            key,
            "L",
            "Analysis span",
            "Span length entered for the active Load Analysis beam model.",
            "m",
            "Load / analysis",
        ),
        "M_uls": _spec(
            key,
            "M^*",
            "Resolved ULS moment",
            "Resolved ultimate moment consumed by the active Load Analysis result.",
            "kNm",
            "Design actions",
        ),
        "V_uls": _spec(
            key,
            "V^*",
            "Resolved ULS shear",
            "Resolved ultimate shear consumed by the active Load Analysis result.",
            "kN",
            "Design actions",
        ),
        "M_sls": _spec(
            key,
            "M_s",
            "Resolved SLS moment",
            "Resolved service moment consumed by the active Load Analysis result.",
            "kNm",
            "Design actions",
        ),
        "V_sls": _spec(
            key,
            "V_s",
            "Resolved SLS shear",
            "Resolved service shear consumed by the active Load Analysis result.",
            "kN",
            "Design actions",
        ),
        "sfd_span_count": _spec(
            key,
            "n_{span}",
            "Number of spans",
            "Number of spans in the active multi-span beam model.",
            "items",
            "Load / analysis",
        ),
        "sfd_point_load_count": _spec(
            key,
            "n_P",
            "Number of point loads",
            "Number of point-load rows in the active single-span case.",
            "items",
            "Load / analysis",
        ),
        "sfd_ms_point_count": _spec(
            key,
            "n_P",
            "Number of point loads",
            "Number of point-load rows in the active multi-span model.",
            "items",
            "Load / analysis",
        ),
        "sfd_ms_udl_count": _spec(
            key,
            "n_{UDL}",
            "Number of UDL segments",
            "Number of uniformly distributed load segments in the active multi-span model.",
            "items",
            "Load / analysis",
        ),
        "sfd_case": _spec(
            key,
            "case",
            "Loading condition",
            "Loading condition selected for the active beam analysis model.",
            None,
            "Load / analysis",
            "Loading condition",
        ),
        "manual_uls_Vstar": _spec(
            key,
            "V^*",
            "Manual ULS shear action",
            "Manual ultimate shear action entered for the Beam Inputs ULS load set.",
            "kN",
            "Design actions",
        ),
        "manual_sls_Vstar": _spec(
            key,
            "V_s",
            "Manual SLS shear action",
            "Manual service shear action entered for the Beam Inputs SLS load set.",
            "kN",
            "Design actions",
        ),
        "manual_uls_Nstar": _spec(
            key,
            "N^*",
            "Manual ULS axial action",
            "Manual ultimate axial action entered for the Beam Inputs ULS load set.",
            "kN",
            "Design actions",
        ),
        "manual_sls_Nstar": _spec(
            key,
            "N_s",
            "Manual SLS axial action",
            "Manual service axial action entered for the Beam Inputs SLS load set.",
            "kN",
            "Design actions",
        ),
        "inputs_detailed_mode": _spec(
            key,
            "mode",
            "Design mode",
            "Fast or detailed Beam Inputs workspace mode.",
            None,
            "Method / assumptions",
        ),
        "optimisation_lock_geometry": _spec(
            key,
            "lock",
            "Lock geometry",
            "Whether the existing geometry is protected from automatic design updates.",
            None,
            "Method / assumptions",
        ),
    }
    if key in canonical_metadata:
        return canonical_metadata[key]

    symbol_map = {
        "uls_Mstar": "M^*",
        "sls_Mstar": "M_s",
        "uls_Vstar": "V^*",
        "sls_Vstar": "V_s",
        "uls_Nstar": "N^*",
        "sls_Nstar": "N_s",
        "Tu_star": "T^*",
        "P_star": "P^*",
        "t_creep": "t_{creep}",
        "t_shrink": "t_{shrink}",
        "phi_bend": "φ",
        "phi_shear": "φ_v",
        "phi_torsion": "φ_t",
        "actions_source": "source",
        "actions_mode": "mode",
        "design_actions_source": "source",
        "defl_beff": "b_{eff}",
        "defl_Ief_user": "I_{ef,user}",
        "defl_limit_ratio": "L/Δ",
        "s_bar_bot": "s_{bar,bot}",
        "n_ducts": "n_{duct}",
        "duct_dia": "d_{duct}",
    }
    unit_map = {
        "b": "mm", "D": "mm", "L": "mm", "bf": "mm", "tf": "mm", "bw": "mm", "tw": "mm",
        "fc": "MPa", "fsy": "MPa", "Ec": "MPa", "Es": "MPa",
        "cover_bot": "mm", "cover_top": "mm", "cover_side": "mm", "side_cover_bot": "mm", "side_cover_top": "mm", "lig_d": "mm", "s_lig": "mm",
        "d_g": "mm", "t_creep": "days", "t_shrink": "days", "age_at_loading": "days", "s_bar_bot": "mm", "n_ducts": "ducts", "duct_dia": "mm",
        "uls_Mstar": "kNm", "sls_Mstar": "kNm", "uls_Vstar": "kN", "sls_Vstar": "kN",
        "uls_Nstar": "kN", "sls_Nstar": "kN", "N_star": "kN", "P_star": "kN", "Tu_star": "kNm",
        "span_L_m": "m", "sfd_span_L_m": "m", "sfd_L_m": "m", "g_udl_kNm_per_m": "kN/m", "q_udl_kNm_per_m": "kN/m",
        "w_sls_kNm_per_m": "kN/m", "w_uls_kNm_per_m": "kN/m", "G_point_kN": "kN", "Q_point_kN": "kN",
        "P_sls_kN": "kN", "P_uls_kN": "kN", "a_m": "m", "a_udl_m": "m", "a_cant_m": "m", "a_overhang_m": "m",
        "crack_theta_deg": "°", "shrinkage_relative_humidity_percent": "%",
    }
    lowered = key.lower()

    # Sustained factors are dimensionless.  Handle them before the generic
    # name-based unit inference, which would otherwise mistake ``udl`` in a
    # key such as ``load_psi_udl`` for a line load.
    if key in {
        "psi_udl",
        "psi_point",
        "load_psi_udl",
        "load_psi_point",
    }:
        return _spec(
            key,
            "ψ_s",
            "Sustained factor",
            "Portion of the variable action treated as sustained for serviceability effects.",
            None,
            "Load / analysis",
        )

    # Repeating longitudinal reinforcement rows.
    row_match = re.match(r"^(bot|top)_row_(\d+)_(mode|bars|spacing|dia)$", key)
    if row_match:
        face, row, field = row_match.groups()
        face_label = "Bottom Reinforcement" if face == "bot" else "Top Reinforcement"
        face_subject = "bottom" if face == "bot" else "top"
        if field == "mode":
            return _spec(
                key,
                f"layout_{{{face},{row}}}",
                f"{face_label} — Layer {row} — Layout",
                f"Whether {face_subject} longitudinal reinforcement layer {row} is specified by bar count or spacing.",
                None,
                "Reinforcement",
            )
        if field == "bars":
            return _spec(
                key,
                f"n_{{{face},{row}}}",
                f"{face_label} — Layer {row} — Bars",
                f"Number of bars in {face_subject} longitudinal reinforcement layer {row}.",
                "bars",
                "Reinforcement",
            )
        if field == "spacing":
            return _spec(
                key,
                f"s_{{{face},{row}}}",
                f"{face_label} — Layer {row} — Spacing",
                f"Centre-to-centre spacing of {face_subject} longitudinal reinforcement layer {row}.",
                "mm",
                "Reinforcement",
            )
        return _spec(
            key,
            f"d_{{b,{face},{row}}}",
            f"{face_label} — Layer {row} — Ø (mm)",
            f"Nominal diameter of {face_subject} longitudinal reinforcement layer {row}.",
            "mm",
            "Reinforcement",
        )

    # T/I flange reinforcement groups repeat the same small set of fields.
    flange_match = re.match(
        r"^(top|bot)_flange_(left|right|transverse)_(enabled|mirror_lr|count|dia|rows|row_spacing|clear_spacing_mode|spacing|legs)$",
        key,
    )
    if flange_match:
        face, side, field = flange_match.groups()
        face_label = "top" if face == "top" else "bottom"
        side_label = side.replace("_", " ")
        subject = f"{face_label} flange {side_label} reinforcement"
        if field in {"enabled", "mirror_lr", "clear_spacing_mode"}:
            name = {
                "enabled": f"{subject.title()} enabled",
                "mirror_lr": f"Mirror {face_label} flange reinforcement left/right",
                "clear_spacing_mode": f"{subject.title()} layout mode",
            }[field]
            definition = {
                "enabled": f"Whether {subject} is included in the section reinforcement layout.",
                "mirror_lr": f"Whether the {face_label} flange reinforcement is mirrored between left and right sides.",
                "clear_spacing_mode": f"Whether {subject} is specified by bar count or clear spacing.",
            }[field]
            return _spec(key, key, name, definition, None, "Reinforcement")
        if field in {"count", "rows", "legs"}:
            units = "bars" if field == "count" else "rows" if field == "rows" else "legs"
            return _spec(
                key,
                f"n_{{{face[0]},{side[0]},{field}}}",
                f"{subject.title()} {field}",
                f"{field.title()} used for the {subject} detailing configuration.",
                units,
                "Reinforcement",
            )
        if field == "dia":
            return _spec(key, f"d_{{b,{face[0]},{side[0]}}}", f"{subject.title()} diameter", f"Nominal bar diameter for the {subject}.", "mm", "Reinforcement")
        return _spec(key, f"s_{{{face[0]},{side[0]}}}", f"{subject.title()} spacing", f"Spacing used for the {subject} detailing configuration.", "mm", "Reinforcement")

    if key in {"actions_source", "actions_mode", "design_actions_source", "loads_edit_mode", "sfd_case"}:
        return _spec(key, symbol_map.get(key, "mode"), "Action source or mode", "Selection controlling which authoritative action branch is used by the page.", None, "Method / assumptions")
    if key in {"inputs_detailed_mode", "auto_geometry", "auto_bottom_reo", "auto_shear", "fast_mode_show_3d", "optimisation_lock_geometry", "optimisation_lock_width", "optimisation_lock_depth", "top_flange_reo_enabled", "bot_flange_reo_enabled", "top_flange_mirror_lr", "bot_flange_mirror_lr", "top_flange_transverse_enabled", "bot_flange_transverse_enabled", "shear_auto_design", "shear_optimize_reinforcement", "crack_wall_in_base_zone", "defl_use_simplified_ief", "loads_edit_toggle", "design_section_committed"}:
        return _spec(key, key, key.replace("_", " ").capitalize(), "Boolean option controlling the corresponding existing engineering method or detailing configuration.", None, "Method / assumptions")
    if key in {"design_optimisation_goal", "k_d_option", "k_v_method", "crack_diagram_panel", "exposure_class", "crack_member_type", "crack_control_method", "member_faces_exposed", "shrinkage_env", "shrinkage_method", "shrinkage_cement_class", "env_option", "design_beam_system_mode", "design_support_condition"} or "support_type_" in key:
        return _spec(key, key, key.replace("_", " ").capitalize(), "Selection controlling the existing engineering method, loading model, or page convention.", None, "Method / assumptions")
    if key == "defl_beff":
        return _spec(key, "b_{eff}", "Effective flange width", "Effective flange width used by the deflection section model.", "mm", "Section geometry")
    if key == "n_ducts":
        return _spec(key, "n_{duct}", "Number of ducts", "Number of ducts crossing the effective web used by the shear/torsion model.", "ducts", "Section geometry")
    if key == "duct_dia":
        return _spec(key, "d_{duct}", "Duct diameter", "Nominal diameter of a duct crossing the effective web.", "mm", "Section geometry")
    if key == "s_bar_bot":
        return _spec(key, "s_{bar,bot}", "Bottom crack-control bar spacing", "Spacing of the bottom bars used by the crack-control calculation.", "mm", "Reinforcement")
    if key in {"design_ms_point_count", "design_ms_udl_count"}:
        load_kind = "point loads" if key.endswith("point_count") else "UDLs"
        return _spec(key, "n", f"Number of design {load_kind}", f"Number of {load_kind} included in the active multi-span load model.", "items", "Load / analysis")

    load_row_match = re.match(
        r"^(design_ms|load_ms)_(G|Q|g|q)_(\d+)$", key
    )
    if load_row_match:
        family, load_type, index = load_row_match.groups()
        is_point = load_type.isupper()
        load_name = "Permanent" if load_type.lower() == "g" else "Variable"
        load_kind = "point load" if is_point else "UDL"
        units = "kN" if is_point else "kN/m"
        symbol = f"{load_type}_{{{index}}}"
        return _spec(
            key,
            symbol,
            f"{load_name} {load_kind} {index}",
            f"{load_name.lower()} {load_kind} {index} consumed by the {family.replace('_', ' ')} loading model.",
            units,
            "Design actions",
        )

    position_row_match = re.match(r"^(design_ms|load_ms)_(x0|x1|x)_(\d+)$", key)
    if position_row_match:
        family, position, index = position_row_match.groups()
        position_name = {
            "x0": "start",
            "x1": "end",
            "x": "position",
        }[position]
        return _spec(
            key,
            f"x_{{{position},{index}}}",
            f"{family.replace('_', ' ').title()} {position_name} {index}",
            f"Distance defining the {position_name} of load row {index} in the {family.replace('_', ' ')} model.",
            "m",
            "Design actions",
        )

    point_row_match = re.match(r"^design_point_(G|Q|x)_(\d+)$", key)
    if point_row_match:
        load_type, index = point_row_match.groups()
        if load_type == "x":
            return _spec(
                key,
                f"x_{{{index}}}",
                f"Point load {index} location",
                f"Distance locating point load {index} from the reference support.",
                "m",
                "Design actions",
            )
        load_name = "Permanent" if load_type == "G" else "Variable"
        return _spec(
            key,
            f"{load_type}_{{{index}}}",
            f"{load_name} point load {index}",
            f"{load_name.lower()} point load {index} applied in the active load model.",
            "kN",
            "Design actions",
        )

    load_point_match = re.match(r"^load_(G|Q|x)_point(?:_(\d+))?$", key)
    if load_point_match:
        load_type, index = load_point_match.groups()
        row_suffix = f" {index}" if index else ""
        if load_type == "x":
            return _spec(
                key,
                f"x_{{{index}}}" if index else "x",
                f"Point load{row_suffix} location",
                "Distance locating the active point load from the reference support.",
                "m",
                "Load / analysis",
            )
        load_name = "Dead" if load_type == "G" else "Live"
        return _spec(
            key,
            f"{load_type}_{{{index}}}" if index else load_type,
            f"{load_name} point load{row_suffix}",
            f"{load_name.lower()} point load used by the active beam analysis model.",
            "kN",
            "Design actions",
        )

    span_row_match = re.match(r"^design_span_len_(\d+)$", key)
    if span_row_match:
        index = span_row_match.group(1)
        return _spec(
            key,
            f"L_{{{index}}}",
            f"Span {index} length",
            f"Length of analysis span {index} in the active multi-span model.",
            "m",
            "Load / analysis",
        )

    category = "Method / assumptions"
    if any(token in lowered for token in ("cover", "shape", "width", "depth", "span", "diameter", "thickness", "web", "flange", "section", "support")):
        category = "Section geometry"
    elif any(token in lowered for token in ("reo", "bar", "bot", "top", "lig", "stirrup", "asv", "row", "duct")):
        category = "Reinforcement"
    elif any(token in lowered for token in ("moment", "mstar", "shear", "vstar", "nstar", "tu", "point", "udl", "load", "psi", "gamma", "design_ms", "design_point", "load_ms", "load_point")):
        category = "Design actions"
    elif any(token in lowered for token in ("fc", "fsy", "ec", "es", "cement", "aggregate", "f_po")):
        category = "Materials"
    elif any(token in lowered for token in ("creep", "shrink", "humidity", "environment", "exposed", "age", "time")):
        category = "Serviceability"
    units = unit_map.get(key)
    if units is None:
        if key.startswith(("design_ms_g_", "design_ms_q_", "load_ms_g_", "load_ms_q_")):
            units = "kN/m"
        elif key.startswith(("design_ms_G_", "design_ms_Q_", "load_ms_G_", "load_ms_Q_", "load_G_point", "load_Q_point")):
            units = "kN"
        elif key.startswith(("design_ms_x", "load_ms_x", "load_x_point", "design_point_x", "sfd_span_L")) or key.endswith("_x_m"):
            units = "m"
        elif key.endswith("_count") or key.endswith("_bars") or key.startswith(("nb_", "n_")):
            units = "bars" if any(token in lowered for token in ("bar", "reo")) else "items"
        elif key.endswith(("_legs",)) or "_legs" in key:
            units = "legs"
        elif key.endswith("_rows"):
            units = "rows"
        elif any(token in lowered for token in ("diameter", "_dia", "spacing", "thickness", "cover", "beff", "duct")):
            units = "mm"
        elif "point" in lowered and any(token in lowered for token in ("load", "g_", "q_", "p_")):
            units = "kN"
        elif "udl" in lowered:
            units = "kN/m"
        elif lowered.endswith(("_x", "_x0", "_x1")) or "position" in lowered or "cursor_x" in lowered:
            units = "m"
        elif key.endswith(("_percent", "_ratio")):
            units = "%" if key.endswith("_percent") else None
        elif key.endswith("_c"):
            units = "°C"
    pretty = re.sub(r"(?<!^)(?=[A-Z])", " ", key).replace("_", " ").strip().capitalize()
    if "Mstar" in key or key.endswith("_M"):
        symbol_map.setdefault(key, "M_s" if key.startswith("sls") else "M^*")
        units = units or "kNm"
    elif "Vstar" in key or key.endswith("_V"):
        symbol_map.setdefault(key, "V_s" if key.startswith("sls") else "V^*")
        units = units or "kN"
    elif "Nstar" in key:
        symbol_map.setdefault(key, "N^*")
        units = units or "kN"
    elif "_point_" in key and key.split("_point_", 1)[-1].startswith(("G", "Q")):
        units = units or "kN"
    elif "_span_len_" in key:
        units = units or "m"

    if key.endswith("_c") and "alpha_micro" not in key:
        units = units or "°C"
    if "alpha_micro_per_c" in key:
        units = "μɛ/°C"
    if "autogenous_" in key or "tensile_capacity_micro" in key:
        units = "μɛ"

    if category == "Section geometry" and any(token in lowered for token in ("support", "span")):
        definition = "Support or span geometry used by the current analysis model."
    elif category == "Materials":
        definition = "Material parameter consumed by the current engineering calculation."
    elif category == "Reinforcement":
        definition = "Reinforcement parameter consumed by the current section or detailing calculation."
    elif category == "Design actions":
        definition = "Design action or load parameter consumed by the current calculation."
    elif category == "Serviceability":
        definition = "Serviceability parameter consumed by the current time-dependent or crack-control calculation."
    else:
        definition = "Method, selection, or analysis parameter consumed by the current engineering calculation."
    return _spec(
        key,
        symbol_map.get(key, pretty),
        pretty,
        definition,
        units,
        category,
    )


def build_start_reference(values: Mapping[str, Any] | None = None) -> PageReferenceModel:
    del values
    return PageReferenceModel(page_key="start", items=())


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "on", "included", "1"}:
            return True
        if lowered in {"false", "no", "off", "not included", "0", ""}:
            return False
    if value is None:
        return default
    return bool(value)


def _inputs_page_visible_keys(values: Mapping[str, Any]) -> set[str]:
    """Return the canonical inputs actually represented by the Inputs page.

    ``BEAM_PROJECT_PARAM_KEYS`` is deliberately broader than the visible
    Inputs editor because it also carries values for downstream pages.  The
    sidebar keeps the canonical contract for storage/coverage, but only
    exposes the active editor fields here.  This prevents stale Load Analysis
    rows and legacy reinforcement aliases from appearing as if they were
    Inputs-page controls.
    """

    source = _with_row_model_aliases(values)
    detailed = _as_bool(
        source.get(
            "reference_inputs_detailed_mode",
            source.get("inputs_detailed_mode", False),
        )
    )
    selected_mode = str(
        source.get(
            "reference_loads_edit_mode",
            source.get("loads_edit_mode", "ULS"),
        )
        or "ULS"
    ).strip().upper()
    selected_prefix = "sls" if selected_mode == "SLS" else "uls"

    visible = {
        item[0]
        for item in _active_section_geometry_specs(
            source,
            include_span=True,
            include_covers=True,
            include_side_cover=detailed,
        )
    }
    visible.update(
        {
            "fc",
            "fsy",
            "actions_source",
            "loads_edit_mode",
            "design_optimisation_goal",
            "optimisation_lock_geometry",
            "inputs_detailed_mode",
            "Tu_star",
            f"{selected_prefix}_Mstar_pos_manual",
            f"manual_{selected_prefix}_Vstar",
            f"manual_{selected_prefix}_Nstar",
            "rowgap_bot",
            "rowgap_top",
            "lig_d",
            "lig_legs",
            "s_lig",
        }
    )
    if detailed:
        visible.update(
            {
                f"{selected_prefix}_Mstar_neg_manual",
                "P_star",
                "member_faces_exposed",
                "shrinkage_env",
                "env_option",
                "defl_support_type",
                "defl_limit_ratio",
                "d_g",
                "k_v_method",
                "exposure_class",
                "crack_member_type",
                "crack_k1",
                "crack_k2",
                "t_creep",
                "age_at_loading",
                "t_shrink",
                "n_ducts",
                "duct_dia",
                "k_d_option",
            }
        )

    visible.update(
        item[0]
        for item in _active_longitudinal_row_specs(source)
    )

    shape = str(source.get("sec_shape") or "RECT").strip().upper()
    if shape in {"T", "I"}:
        visible.update(
            {
                "top_flange_reo_enabled",
                "bot_flange_reo_enabled",
                "top_flange_mirror_lr",
                "bot_flange_mirror_lr",
                "top_flange_left_count",
                "top_flange_left_dia",
                "top_flange_left_rows",
                "top_flange_left_row_spacing",
                "top_flange_left_clear_spacing_mode",
                "bot_flange_left_count",
                "bot_flange_left_dia",
                "bot_flange_left_rows",
                "bot_flange_left_row_spacing",
                "bot_flange_left_clear_spacing_mode",
                "top_flange_transverse_enabled",
                "bot_flange_transverse_enabled",
                "top_flange_transverse_dia",
                "bot_flange_transverse_dia",
                "top_flange_transverse_spacing",
                "bot_flange_transverse_spacing",
                "top_flange_transverse_legs",
                "bot_flange_transverse_legs",
            }
        )
        if not _as_bool(source.get("top_flange_mirror_lr"), default=True):
            visible.update(
                {
                    "top_flange_right_count",
                    "top_flange_right_dia",
                    "top_flange_right_rows",
                    "top_flange_right_row_spacing",
                    "top_flange_right_clear_spacing_mode",
                }
            )
        if not _as_bool(source.get("bot_flange_mirror_lr"), default=True):
            visible.update(
                {
                    "bot_flange_right_count",
                    "bot_flange_right_dia",
                    "bot_flange_right_rows",
                    "bot_flange_right_row_spacing",
                    "bot_flange_right_clear_spacing_mode",
                }
            )
    return visible


_INPUTS_RUNTIME_SPECS = (
    _spec(
        "loads_edit_mode",
        "load set",
        "SLS load view",
        "Whether the Beam Inputs action editor is currently showing the ULS or SLS load set.",
        None,
        "Method / assumptions",
        "View SLS loads",
    ),
)


def build_beam_inputs_reference(values: Mapping[str, Any]) -> PageReferenceModel:
    from state_and_helpers import BEAM_PROJECT_PARAM_KEYS

    source = _with_row_model_aliases(_clean_mapping(values))
    reinforcement_display_values = _reinforcement_display_values(source)
    source.update(
        {
            key: reinforcement_display_values[key]
            for key in ("bot_reinforcement_notation", "top_reinforcement_notation")
        }
    )
    specs = (
        tuple(_parameter_spec(str(key)) for key in BEAM_PROJECT_PARAM_KEYS)
        + _INPUTS_RUNTIME_SPECS
        + _active_reinforcement_notation_specs()
    )
    visible_keys = _inputs_page_visible_keys(source)
    hidden_keys = set(str(key) for key in BEAM_PROJECT_PARAM_KEYS) - visible_keys
    visible_keys.update(
        {"bot_reinforcement_notation", "top_reinforcement_notation"}
    )
    return _model(
        "inputs",
        source,
        specs,
        source_label=str(source.get("reference_source") or "Beam Inputs"),
        display_values={
            "actions_source": (
                "On"
                if str(source.get("actions_source") or "").strip().lower()
                in {
                    "design",
                    "teaching",
                    "teaching sfd/bmd page (|m|max, |v|max)",
                    "load analysis",
                    "load analysis actions",
                }
                else "Off"
            ),
            "inputs_detailed_mode": (
                "Detailed"
                if _as_bool(source.get("inputs_detailed_mode"))
                else "Fast"
            ),
            "optimisation_lock_geometry": (
                "On"
                if _as_bool(source.get("optimisation_lock_geometry"))
                else "Off"
            ),
            "design_optimisation_goal": {
                "balanced": "Balanced design",
                "shallower_beam": "Shallower beam",
                "less_longitudinal_reinforcement": "Less longitudinal reinforcement",
                "less_shear_reinforcement": "Less shear reinforcement",
            }.get(
                str(source.get("design_optimisation_goal") or "").strip().lower(),
                str(source.get("design_optimisation_goal") or UNAVAILABLE),
            ),
            "loads_edit_mode": (
                "On (SLS loads)"
                if str(source.get("loads_edit_mode") or "ULS").strip().upper()
                == "SLS"
                else "Off (ULS loads)"
            ),
            **reinforcement_display_values,
        },
        hidden_keys=hidden_keys,
    )


_LOAD_ANALYSIS_SPECS = (
    _spec("beam_system_mode", "system", "Beam system mode", "Single-span or multi-span structural idealisation used by Load Analysis.", None, "Load / analysis"),
    _spec("load_case", "case", "Loading case", "Support and loading case used to solve reactions, shear and moment diagrams.", None, "Load / analysis"),
    _spec("support_condition", "supports", "Support condition", "Support fixity or restraint condition used by the beam model.", None, "Load / analysis"),
    _spec("L_m", "L", "Analysis span", "Span length used by the active Load Analysis model.", "m", "Load / analysis"),
    _spec("g_udl_kNm_per_m", "g", "Permanent UDL", "Unfactored permanent uniformly distributed load.", "kN/m", "Design actions"),
    _spec("q_udl_kNm_per_m", "q", "Variable UDL", "Unfactored variable uniformly distributed load.", "kN/m", "Design actions"),
    _spec("psi_udl", "ψ_{UDL}", "UDL sustained factor", "Serviceability combination factor applied to the variable UDL.", None, "Load / analysis"),
    _spec("G_point_kN", "G", "Permanent point load", "Unfactored permanent point load.", "kN", "Design actions"),
    _spec("Q_point_kN", "Q", "Variable point load", "Unfactored variable point load.", "kN", "Design actions"),
    _spec("psi_point", "ψ_P", "Point-load sustained factor", "Serviceability combination factor applied to the variable point load.", None, "Load / analysis"),
    _spec("a_m", "a", "Point-load location", "Distance from the relevant support used for a point load.", "m", "Load / analysis"),
    _spec("a_udl_m", "a_{UDL}", "Partial UDL length", "Length of a partial uniformly distributed load.", "m", "Load / analysis"),
    _spec("a_cant_m", "a_{cant}", "Cantilever load location", "Point-load location measured from the cantilever fixed end.", "m", "Load / analysis"),
    _spec("a_overhang_m", "a_{oh}", "Overhang length", "Length of the overhang beyond the internal support.", "m", "Load / analysis"),
    _spec("design_actions_source", "source", "Design action source", "Whether the design actions are absolute maxima or taken at a selected design section.", None, "Method / assumptions"),
    _spec("active_mode", "mode", "Active load combination", "ULS or SLS combination currently selected for the teaching derivation.", None, "Method / assumptions"),
    _spec("M_uls", "M^*", "Resolved ULS moment", "Resolved ultimate moment maximum from the active load-analysis result.", "kNm", "Design actions"),
    _spec("V_uls", "V^*", "Resolved ULS shear", "Resolved ultimate shear maximum from the active load-analysis result.", "kN", "Design actions"),
    _spec("M_sls", "M_s", "Resolved SLS moment", "Resolved service moment maximum from the active load-analysis result.", "kNm", "Design actions"),
    _spec("V_sls", "V_s", "Resolved SLS shear", "Resolved service shear maximum from the active load-analysis result.", "kN", "Design actions"),
)

_LOAD_ANALYSIS_SPECS_BY_KEY = {item[0]: item for item in _LOAD_ANALYSIS_SPECS}


_LOAD_ANALYSIS_RUNTIME_SPECS: dict[str, ReferenceSpec] = {
    "sfd_beam_system_mode": _spec(
        "sfd_beam_system_mode",
        "system",
        "Beam system mode",
        "Single-span or multi-span structural idealisation used by Load Analysis.",
        None,
        "Load / analysis",
        "Beam system mode",
    ),
    "sfd_case": _spec(
        "sfd_case",
        "case",
        "Loading condition",
        "Support and loading case used to solve reactions, shear and moment diagrams.",
        None,
        "Load / analysis",
        "Loading condition",
    ),
    "sfd_support_condition": _spec(
        "sfd_support_condition",
        "supports",
        "Support condition",
        "Support fixity or restraint condition used by the single-span beam model.",
        None,
        "Load / analysis",
        "Support condition",
    ),
    "sfd_L_m": _spec(
        "sfd_L_m",
        "L",
        "Span L",
        "Span length used by the active single-span Load Analysis model.",
        "m",
        "Load / analysis",
        "Span L (m)",
    ),
    "sfd_span_count": _spec(
        "sfd_span_count",
        "n_{span}",
        "Number of spans",
        "Number of spans in the active multi-span beam model.",
        "items",
        "Load / analysis",
        "Number of spans",
    ),
    "load_g_udl": _spec(
        "load_g_udl",
        "g",
        "Dead UDL",
        "Permanent uniformly distributed load entered for the active beam case.",
        "kN/m",
        "Design actions",
        "Dead UDL g (kN/m)",
    ),
    "load_q_udl": _spec(
        "load_q_udl",
        "q",
        "Live UDL",
        "Variable uniformly distributed load entered for the active beam case.",
        "kN/m",
        "Design actions",
        "Live UDL q (kN/m)",
    ),
    "load_psi_udl": _spec(
        "load_psi_udl",
        "ψ_s",
        "Sustained factor",
        "Portion of the variable UDL treated as sustained for serviceability effects.",
        None,
        "Load / analysis",
    ),
    "load_psi_point": _spec(
        "load_psi_point",
        "ψ_s",
        "Sustained factor",
        "Portion of the variable point load treated as sustained for serviceability effects.",
        None,
        "Load / analysis",
        "Sustained factor ψ_s for point load",
    ),
    "sfd_a_udl": _spec(
        "sfd_a_udl",
        "a",
        "Partial UDL length",
        "Length of the partial uniformly distributed load from the left.",
        "m",
        "Load / analysis",
        "UDL length a from left (m)",
    ),
    "sfd_point_load_count": _spec(
        "sfd_point_load_count",
        "n_P",
        "Number of point loads",
        "Number of point-load rows in the active single-span case.",
        "items",
        "Load / analysis",
        "Number of point loads",
    ),
    "load_G_point": _spec(
        "load_G_point",
        "G",
        "Dead point load",
        "Permanent point load in the active single-point case.",
        "kN",
        "Design actions",
        "Dead point load G (kN)",
    ),
    "load_Q_point": _spec(
        "load_Q_point",
        "Q",
        "Live point load",
        "Variable point load in the active single-point case.",
        "kN",
        "Design actions",
        "Live point load Q (kN)",
    ),
    "load_a_point": _spec(
        "load_a_point",
        "a",
        "Point-load distance",
        "Distance of the point load from the left support.",
        "m",
        "Load / analysis",
        "Distance a from left support (m)",
    ),
    "sfd_a_cant": _spec(
        "sfd_a_cant",
        "a",
        "Point-load distance",
        "Distance of the point load from the cantilever fixed end.",
        "m",
        "Load / analysis",
        "Distance a from fixed end (m)",
    ),
    "sfd_a_overhang": _spec(
        "sfd_a_overhang",
        "a",
        "Overhang length",
        "Length of the right overhang beyond the internal support.",
        "m",
        "Load / analysis",
        "Overhang length a (m)",
    ),
    "design_section_x_m": _spec(
        "design_section_x_m",
        "x",
        "Design section location",
        "Selected section location used when design actions are taken at a section rather than absolute maxima.",
        "m",
        "Load / analysis",
        "Section location x (m)",
    ),
}


def _load_analysis_runtime_spec(key: str) -> ReferenceSpec:
    return _LOAD_ANALYSIS_RUNTIME_SPECS.get(key, _parameter_spec(key))


def _copy_first_present(
    source: dict[str, Any],
    target: str,
    *aliases: str,
) -> None:
    if target in source:
        return
    for alias in aliases:
        if alias in source:
            source[target] = source[alias]
            return


def _load_analysis_page_source(values: Mapping[str, Any]) -> dict[str, Any]:
    """Normalise existing Load Analysis aliases into the active widget keys."""

    source = _clean_mapping(values)
    _copy_first_present(source, "beam_system_mode", "sfd_beam_system_mode")
    _copy_first_present(source, "load_case", "sfd_case")
    _copy_first_present(
        source,
        "support_condition",
        "sfd_support_condition",
        "design_support_condition",
    )
    _copy_first_present(source, "L_m", "sfd_L_m", "span_L_m", "load_L")
    _copy_first_present(
        source,
        "design_actions_source",
        "design_actions_source_selector",
    )
    _copy_first_present(source, "design_section_x_m", "section_cursor_x_m")
    _copy_first_present(source, "load_g_udl", "g_udl_kNm_per_m")
    _copy_first_present(source, "load_q_udl", "q_udl_kNm_per_m")
    _copy_first_present(source, "load_psi_udl", "psi_udl")
    _copy_first_present(source, "load_psi_point", "psi_point")
    _copy_first_present(source, "load_G_point", "G_point_kN")
    _copy_first_present(source, "load_Q_point", "Q_point_kN")
    _copy_first_present(source, "load_a_point", "a_m")
    _copy_first_present(source, "sfd_a_udl", "a_udl_m")
    _copy_first_present(source, "sfd_a_cant", "a_cant_m")
    _copy_first_present(source, "sfd_a_overhang", "a_overhang_m")
    for target, aliases in {
        "sfd_span_count": ("design_span_count",),
        "sfd_ms_point_count": ("design_ms_point_count",),
        "sfd_ms_udl_count": ("design_ms_udl_count",),
    }.items():
        _copy_first_present(source, target, *aliases)
    for index in range(1, 9):
        for target, aliases in {
            f"sfd_span_len_{index}": (f"design_span_len_{index}",),
            f"sfd_support_type_{index}": (f"design_support_type_{index}",),
            f"load_ms_G_{index}": (f"design_ms_G_{index}",),
            f"load_ms_Q_{index}": (f"design_ms_Q_{index}",),
            f"load_ms_g_{index}": (f"design_ms_g_{index}",),
            f"load_ms_q_{index}": (f"design_ms_q_{index}",),
            f"load_ms_x_{index}": (f"design_ms_x_{index}",),
            f"load_ms_x0_{index}": (f"design_ms_x0_{index}",),
            f"load_ms_x1_{index}": (f"design_ms_x1_{index}",),
            f"load_G_point_{index}": (f"design_point_G_{index}",),
            f"load_Q_point_{index}": (f"design_point_Q_{index}",),
            f"load_x_point_{index}": (f"design_point_x_{index}",),
        }.items():
            _copy_first_present(source, target, *aliases)
    return source


def _load_analysis_page_specs(values: Mapping[str, Any]) -> tuple[ReferenceSpec, ...]:
    """Return only the controls rendered for the current load case."""

    source = _load_analysis_page_source(values)
    keys: list[str] = [
        "beam_system_mode",
        "load_case",
        "support_condition",
        "L_m",
        "actions_source",
        "design_actions_source",
        "active_mode",
        "M_uls",
        "V_uls",
        "M_sls",
        "V_sls",
    ]

    def add(key: str) -> None:
        if key in source and key not in keys:
            keys.append(key)

    mode = str(source.get("beam_system_mode") or "Single span").strip().lower()
    case = str(source.get("load_case") or "").strip().lower()
    if "multi" in mode:
        add("load_psi_point")
        add("load_psi_udl")
        try:
            span_count = max(0, min(5, int(float(source.get("sfd_span_count", 0) or 0))))
        except (TypeError, ValueError):
            span_count = 0
        add("sfd_span_count")
        for index in range(1, span_count + 1):
            add(f"sfd_span_len_{index}")
        for index in range(1, span_count + 2):
            add(f"sfd_support_type_{index}")
        try:
            point_count = max(0, min(8, int(float(source.get("sfd_ms_point_count", 0) or 0))))
        except (TypeError, ValueError):
            point_count = 0
        try:
            udl_count = max(0, min(8, int(float(source.get("sfd_ms_udl_count", 0) or 0))))
        except (TypeError, ValueError):
            udl_count = 0
        add("sfd_ms_point_count")
        for index in range(1, point_count + 1):
            for field in ("G", "Q", "x"):
                add(f"load_ms_{field}_{index}")
        add("sfd_ms_udl_count")
        for index in range(1, udl_count + 1):
            for field in ("g", "q", "x0", "x1"):
                add(f"load_ms_{field}_{index}")
    elif "udl" in case:
        for key in ("load_g_udl", "load_q_udl", "load_psi_udl"):
            add(key)
        if "partial" in case:
            add("sfd_a_udl")
    elif "point" in case or "overhang" in case:
        add("load_psi_point")
        if "multiple point" in case:
            try:
                point_count = max(0, min(6, int(float(source.get("sfd_point_load_count", 0) or 0))))
            except (TypeError, ValueError):
                point_count = 0
            add("sfd_point_load_count")
            for index in range(1, point_count + 1):
                for field in ("G", "Q", "x"):
                    add(f"load_{field}_point_{index}")
        else:
            for key in ("load_G_point", "load_Q_point"):
                add(key)
            if "distance a from left" in case:
                add("load_a_point")
            elif "distance a from fixed" in case:
                add("sfd_a_cant")
            elif "overhang" in case:
                add("sfd_a_overhang")

    if str(source.get("design_actions_source") or "").strip().lower() in {
        "section",
        "design section",
    }:
        add("design_section_x_m")

    specs: list[ReferenceSpec] = []
    for key in keys:
        if key in source:
            if key in _LOAD_ANALYSIS_SPECS_BY_KEY:
                specs.append(_LOAD_ANALYSIS_SPECS_BY_KEY[key])
            elif key in _LOAD_ANALYSIS_RUNTIME_SPECS:
                specs.append(_LOAD_ANALYSIS_RUNTIME_SPECS[key])
            else:
                specs.append(_load_analysis_runtime_spec(key))
    return tuple(specs)


def build_load_analysis_reference(values: Mapping[str, Any]) -> PageReferenceModel:
    source = _load_analysis_page_source(values)
    display_values = {}
    action_source = str(source.get("design_actions_source") or "").strip().lower()
    if action_source in {"max", "absolute maxima"}:
        display_values["design_actions_source"] = "Absolute maxima"
    elif action_source in {"section", "design section"}:
        display_values["design_actions_source"] = "Design section"
    return _model(
        "design",
        source,
        _load_analysis_page_specs(source),
        source_label="Load Analysis",
        display_values=display_values,
    )


_BENDING_SPECS = (
    *_COMMON_GEOMETRY,
    *_COMMON_MATERIALS,
    _spec("rowgap_bot", "g_{bot}", "Bottom reinforcement — Row gap", "Clear vertical gap between bottom longitudinal reinforcement rows.", "mm", "Reinforcement", "Row gap"),
    _spec("rowgap_top", "g_{top}", "Top reinforcement — Row gap", "Clear vertical gap between top longitudinal reinforcement rows.", "mm", "Reinforcement", "Row gap"),
    _spec("N_star", "N^*", "Axial force", "Axial force acting with the current bending action.", "kN", "Design actions"),
    _spec("uls_Nstar", "N^*", "Axial force", "Ultimate axial force shown by the active Bending action control.", "kN", "Design actions", "Axial force N* (kN)"),
    _spec("sls_Nstar", "N_s", "Axial force", "Service axial force shown by the active Bending action control.", "kN", "Design actions", "Axial force N* (kN)"),
    _spec("P_star", "P^*", "Prestress force", "Prestress or pre-compression force acting with the current bending action.", "kN", "Design actions"),
    _spec("actions_source", "source", "Design actions source", "Source of the bending actions displayed and consumed by the page.", None, "Method / assumptions"),
    _spec("d", "d", "Effective depth", "Distance from the compression face to the centroid of the tensile reinforcement.", "mm", "Resolved section parameters"),
    _spec("do", "d_o", "Compression reinforcement depth", "Distance from the compression face to the centroid of the compression reinforcement.", "mm", "Resolved section parameters"),
    _spec("Ast_bot", "A_{st,bot}", "Bottom tensile steel area", "Resolved area of bottom longitudinal reinforcement used by the bending page.", "mm²", "Resolved section parameters"),
    _spec("Ast_top", "A_{st,top}", "Top reinforcement area", "Resolved area of top longitudinal reinforcement used by the bending page.", "mm²", "Resolved section parameters"),
    _spec("M_star", "M^*", "Current ULS moment", "ULS moment for the currently selected sagging or hogging detail view.", "kNm", "Design actions"),
    _spec("M_s", "M_s", "Current SLS moment", "SLS moment for the currently selected bending detail view.", "kNm", "Design actions"),
    _spec("uls_Mstar_pos_manual", "M_u^{*+}", "Positive design moment", "Manual sagging design moment input used when the action source is manual.", "kNm", "Design actions"),
    _spec("uls_Mstar_neg_manual", "M_u^{*-}", "Negative design moment", "Manual hogging design moment input used when the action source is manual.", "kNm", "Design actions"),
    _spec("sls_Mstar_pos_manual", "M_s^{+}", "Positive service moment", "Manual sagging service moment input used when the action source is manual.", "kNm", "Design actions"),
    _spec("sls_Mstar_neg_manual", "M_s^{-}", "Negative service moment", "Manual hogging service moment input used when the action source is manual.", "kNm", "Design actions"),
    _spec("moment_sign", "sign", "Moment sign", "Sagging or hogging detail view controlling compression and tension faces.", None, "Method / assumptions"),
    _spec("actions_mode", "actions", "Action source mode", "Whether actions are manually specified or resolved from Load Analysis.", None, "Method / assumptions"),
    _spec("sls_ignore_compression_reinforcement", "SLS C_s", "SLS compression reinforcement option", "Whether compression-side reinforcement is excluded from the cracked SLS section projection.", None, "Method / assumptions"),
    _spec("concrete_stress_model", "stress model", "Concrete stress model", "Concrete stress-block model selected for the bending presentation and associated calculation path.", None, "Method / assumptions"),
    _spec("loads_edit_mode", "load set", "SLS load view", "Whether the Bending action editor is currently showing the ULS or SLS load set.", None, "Method / assumptions", "View SLS loads"),
    _spec("phi_bend", "φ", "Bending strength reduction factor", "Strength reduction factor used by the ULS bending capacity check.", None, "Method / assumptions"),
)


def _bending_page_specs(values: Mapping[str, Any]) -> tuple[ReferenceSpec, ...]:
    """Metadata for the active Bending inputs and resolved equation drivers."""

    keys = {
        item[0]
        for item in _active_section_geometry_specs(
            values,
            include_span=True,
            include_covers=True,
        )
    }
    keys.update(
        {
            "fc",
            "fsy",
            "Ec",
            "Es",
            "rowgap_bot",
            "rowgap_top",
            "N_star",
            "P_star",
            "actions_source",
            "d",
            "do",
            "Ast_bot",
            "Ast_top",
            "M_star",
            "M_s",
            "moment_sign",
            "actions_mode",
            "sls_ignore_compression_reinforcement",
            "concrete_stress_model",
            "loads_edit_mode",
            "phi_bend",
        }
    )
    selected_prefix = (
        "sls"
        if str(values.get("loads_edit_mode") or "ULS").strip().upper() == "SLS"
        else "uls"
    )
    keys.update(
        {
            f"{selected_prefix}_Nstar",
            f"{selected_prefix}_Mstar_pos_manual",
            f"{selected_prefix}_Mstar_neg_manual",
        }
    )
    return _specs_for_keys(_BENDING_SPECS, keys)


def build_bending_reference(values: Mapping[str, Any]) -> PageReferenceModel:
    source = _with_row_model_aliases(_clean_mapping(values))
    display_values = _reinforcement_display_values(source)
    source.update(
        {
            key: display_values[key]
            for key in ("bot_reinforcement_notation", "top_reinforcement_notation")
        }
    )
    specs = (
        _bending_page_specs(source)
        + _active_longitudinal_row_specs(source)
        + _active_reinforcement_notation_specs()
    )
    display_values["sls_ignore_compression_reinforcement"] = (
        "On" if bool(source.get("sls_ignore_compression_reinforcement")) else "Off"
    )
    display_values["actions_mode"] = {
        "design": "Load Analysis actions",
        "manual": "Manual design actions",
    }.get(str(source.get("actions_mode") or "").lower(), "—")
    display_values["concrete_stress_model"] = (
        "On"
        if str(source.get("concrete_stress_model") or "").lower() == "parabolic"
        else "Off"
    )
    selected_load_view = str(source.get("loads_edit_mode") or "ULS").strip().upper()
    display_values["loads_edit_mode"] = (
        "On (SLS loads)" if selected_load_view == "SLS" else "Off (ULS loads)"
    )
    display_values["moment_sign"] = {
        "positive": "Sagging",
        "negative": "Hogging",
        "sagging": "Sagging",
        "hogging": "Hogging",
    }.get(str(source.get("moment_sign") or "").lower(), str(source.get("moment_sign") or "—"))
    return _model(
        "bending",
        source,
        specs,
        source_label=_source_label(source, "Beam Inputs"),
        display_values=display_values,
    )


_SHEAR_SPECS = (
    *_COMMON_GEOMETRY,
    *_COMMON_MATERIALS,
    _spec("d", "d", "Effective depth", "Effective depth used by the shear and torsion checks.", "mm", "Resolved section parameters"),
    _spec("phi_shear", "φ_v", "Shear strength reduction factor", "Strength reduction factor used for shear capacity.", None, "Method / assumptions"),
    _spec("phi_torsion", "φ_t", "Torsion strength reduction factor", "Strength reduction factor used for torsion screening.", None, "Method / assumptions"),
    _spec("V_star", "V^*", "Design shear action", "Design shear action used by the current shear checks.", "kN", "Design actions"),
    _spec("M_star", "M^*", "Design bending action", "Design bending action used in the MCFT longitudinal-strain calculation.", "kNm", "Design actions"),
    _spec("T_star", "T^*", "Design torsion action", "Design torsional action used by torsion and equivalent-shear checks.", "kNm", "Design actions"),
    _spec("N_star", "N^*", "Design axial action", "Design axial action used in the MCFT strain calculation.", "kN", "Design actions"),
    _spec("P_v", "P_v", "Prestress action", "Prestress force used by the shear MCFT action terms.", "kN", "Design actions"),
    _spec("P_star", "P^*", "Prestress force", "Prestress force entered in the optional Shear design-actions control.", "kN", "Design actions", "Prestress force P* (kN)"),
    _spec("uls_Mstar_pos_manual", "M_u^{*+}", "Positive design moment", "Positive design moment shown by the active ULS/Shear action control.", "kNm", "Design actions", "Positive design moment Mu*+ (kNm)"),
    _spec("uls_Mstar_neg_manual", "M_u^{*-}", "Negative design moment", "Negative design moment shown by the active ULS/Shear action control.", "kNm", "Design actions", "Negative design moment Mu*- (kNm)"),
    _spec("sls_Mstar_pos_manual", "M_s^{+}", "Positive design moment", "Positive design moment shown by the active SLS/Shear action control.", "kNm", "Design actions", "Positive design moment Mu*+ (kNm)"),
    _spec("sls_Mstar_neg_manual", "M_s^{-}", "Negative design moment", "Negative design moment shown by the active SLS/Shear action control.", "kNm", "Design actions", "Negative design moment Mu*- (kNm)"),
    _spec("manual_uls_Vstar", "V^*", "Design shear", "Design shear shown by the active ULS/Shear action control.", "kN", "Design actions", "Design shear V* (kN)"),
    _spec("manual_sls_Vstar", "V_s", "Design shear", "Design shear shown by the active SLS/Shear action control.", "kN", "Design actions", "Design shear V* (kN)"),
    _spec("manual_uls_Nstar", "N^*", "Axial force", "Axial force shown by the active ULS/Shear action control.", "kN", "Design actions", "Axial force N* (kN, +tension)"),
    _spec("manual_sls_Nstar", "N_s", "Axial force", "Axial force shown by the active SLS/Shear action control.", "kN", "Design actions", "Axial force N* (kN, +tension)"),
    _spec("A_st", "A_{st}", "Longitudinal tensile steel area", "Longitudinal tensile steel area used by the MCFT strain calculation.", "mm²", "Reinforcement"),
    _spec("A_pt", "A_{pt}", "Prestressing steel area", "Prestressing steel area used by the MCFT action terms.", "mm²", "Reinforcement"),
    _spec("f_po", "f_{po}", "Prestressing steel stress", "Initial prestressing steel stress used by the MCFT action terms.", "MPa", "Materials"),
    _spec("A_ct", "A_{ct}", "Concrete tension area", "Concrete area used by the MCFT longitudinal-strain calculation.", "mm²", "Resolved shear parameters"),
    _spec("sigma_cp", "σ_{cp}", "Concrete axial stress", "Concrete compressive stress due to axial or prestress action.", "MPa", "Resolved shear parameters"),
    _spec("sum_duct", "ΣA_{duct}", "Duct area", "Resolved total duct area deducted from the effective web width.", "mm²", "Resolved shear parameters"),
    _spec("lig_d", "d_{lig}", "Ligature diameter", "Diameter of the shear reinforcement legs.", "mm", "Reinforcement"),
    _spec("lig_legs", "n_{legs}", "Ligature legs", "Number of effective shear reinforcement legs.", "legs", "Reinforcement"),
    _spec("s_lig", "s", "Ligature spacing", "Provided spacing of shear reinforcement.", "mm", "Reinforcement"),
    _spec("Asv", "A_{sv}", "Shear reinforcement area", "Resolved shear reinforcement area used by the reinforcement checks.", "mm²", "Resolved shear parameters"),
    _spec("d_g", "d_g", "Maximum aggregate size", "Maximum aggregate size used by the MCFT aggregate-size factor.", "mm", "Materials"),
    _spec("k_v_method", "k_v method", "Shear method", "Selected simplified or general method for resolving k_v and θ_v.", None, "Method / assumptions"),
    _spec("k_d_option", "k_d", "Duct reduction option", "Selected duct condition used to resolve the web duct factor.", None, "Method / assumptions", "k_d factor for prestressing ducts"),
    _spec("b_v", "b_v", "Effective web width", "Resolved effective web width used by shear capacity equations.", "mm", "Resolved shear parameters"),
    _spec("d_v", "d_v", "Effective shear depth", "Resolved effective shear depth used by shear capacity equations.", "mm", "Resolved shear parameters"),
    _spec("V_eq", "V^*_{eq}", "Equivalent shear action", "Combined shear action including the torsion-equivalent contribution.", "kN", "Resolved shear parameters"),
    _spec("eps_x", "ε_x", "Longitudinal strain", "Longitudinal strain used by the MCFT shear method.", None, "Resolved shear parameters"),
    _spec("k_v", "k_v", "MCFT shear factor", "Resolved shear strength factor from the selected shear method.", None, "Resolved shear parameters"),
    _spec("theta_v_deg", "θ_v", "Compression strut angle", "Resolved compression-strut angle used by the MCFT equations.", "°", "Resolved shear parameters"),
    _spec("crack_theta_deg", "θ", "Reference crack angle", "Reference crack angle used by the torsion screening convention.", "°", "Method / assumptions"),
    _spec("defl_support_type", "support", "Support condition", "Support condition selected for the linked shear/deflection convention.", None, "Method / assumptions", "Support condition (k₂)"),
    _spec("n_ducts", "n_{duct}", "Number of ducts", "Number of prestressing ducts crossing the effective web used by the shear model.", "ducts", "Section geometry", "Number of ducts crossing web"),
    _spec("duct_dia", "d_{duct}", "Duct diameter", "Nominal diameter of each prestressing duct crossing the effective web.", "mm", "Section geometry", "Duct diameter (mm)"),
    _spec("loads_edit_mode", "load set", "SLS load view", "Whether the Shear action editor is currently showing the ULS or SLS load set.", None, "Method / assumptions", "View SLS loads"),
    _spec("shear_include_prestress_effects_ui", "prestress", "Prestress effects option", "Whether the optional prestress action input is shown in the Shear action editor.", None, "Method / assumptions", "Include prestress effects"),
    _spec("shear_auto_design", "auto", "Automatic shear design", "Whether the existing automatic shear-detailing mode is enabled.", None, "Method / assumptions"),
    _spec("actions_mode", "actions", "Action source mode", "Whether current actions are manual or Load Analysis driven.", None, "Method / assumptions"),
)


def _shear_page_specs(values: Mapping[str, Any]) -> tuple[ReferenceSpec, ...]:
    """Metadata for the active Shear inputs and MCFT equation drivers."""

    geometry_specs = _active_section_geometry_specs(
        values,
        include_span=True,
        include_covers=False,
    )
    geometry_keys = {item[0] for item in _COMMON_GEOMETRY}
    non_geometry_keys = {
        item[0] for item in _SHEAR_SPECS
    } - geometry_keys
    selected_prefix = (
        "sls"
        if str(values.get("loads_edit_mode") or "ULS").strip().upper() == "SLS"
        else "uls"
    )
    non_geometry_keys.update(
        {
            f"{selected_prefix}_Mstar_pos_manual",
            f"{selected_prefix}_Mstar_neg_manual",
            f"manual_{selected_prefix}_Vstar",
            f"manual_{selected_prefix}_Nstar",
        }
    )
    for inactive_prefix in {"uls", "sls"} - {selected_prefix}:
        non_geometry_keys.difference_update(
            {
                f"{inactive_prefix}_Mstar_pos_manual",
                f"{inactive_prefix}_Mstar_neg_manual",
                f"manual_{inactive_prefix}_Vstar",
                f"manual_{inactive_prefix}_Nstar",
            }
    )
    if not _as_bool(values.get("shear_include_prestress_effects_ui")):
        non_geometry_keys.discard("P_star")
        non_geometry_keys.discard("P_v")
    else:
        # P_v is the resolved internal name for the same optional P* input;
        # show the page control once rather than presenting two labels for one
        # engineering value.
        non_geometry_keys.discard("P_v")
    support_text = str(values.get("defl_support_type") or "").lower()
    try:
        selected_moment = float(
            values.get(f"{selected_prefix}_Mstar", values.get("M_star", 0.0)) or 0.0
        )
    except (TypeError, ValueError):
        selected_moment = 0.0
    show_negative_moment = (
        any(token in support_text for token in ("continuous", "interior", "fixed"))
        or selected_moment < 0.0
        or str(values.get("bending_detail_view") or "").lower() == "negative"
    )
    if not show_negative_moment:
        non_geometry_keys.discard(f"{selected_prefix}_Mstar_neg_manual")
    return geometry_specs + _specs_for_keys(_SHEAR_SPECS, non_geometry_keys)


def build_shear_reference(values: Mapping[str, Any]) -> PageReferenceModel:
    source = _clean_mapping(values)
    # The Shear editor exposes the active load-set controls through proxy
    # widgets, while the page snapshot publishes the canonical signed action
    # values.  Project the existing values into the reference model so the
    # sidebar can name and display the same controls without owning them.
    for prefix in ("uls", "sls"):
        try:
            signed_moment = float(source.get(f"{prefix}_Mstar", 0.0) or 0.0)
        except (TypeError, ValueError):
            signed_moment = 0.0
        source.setdefault(
            f"{prefix}_Mstar_pos_manual", max(0.0, signed_moment)
        )
        source.setdefault(
            f"{prefix}_Mstar_neg_manual", max(0.0, -signed_moment)
        )
        source.setdefault(f"manual_{prefix}_Vstar", source.get(f"{prefix}_Vstar"))
        source.setdefault(f"manual_{prefix}_Nstar", source.get(f"{prefix}_Nstar"))
    source.setdefault("P_star", source.get("P_v"))
    source.setdefault("P_v", source.get("P_star"))
    display_values = {}
    load_view = str(source.get("loads_edit_mode") or "ULS").strip().upper()
    display_values["loads_edit_mode"] = (
        "On (SLS loads)" if load_view == "SLS" else "Off (ULS loads)"
    )
    display_values["shear_include_prestress_effects_ui"] = (
        "On" if _as_bool(source.get("shear_include_prestress_effects_ui")) else "Off"
    )
    display_values["shear_auto_design"] = (
        "On" if _as_bool(source.get("shear_auto_design")) else "Off"
    )
    display_values["actions_mode"] = {
        "design": "Load Analysis actions",
        "manual": "Manual design actions",
    }.get(str(source.get("actions_mode") or "").lower(), UNAVAILABLE)
    return _model(
        "shear",
        source,
        _shear_page_specs(source),
        source_label=_source_label(source, "Beam Inputs"),
        display_values=display_values,
    )


_CREEP_SPECS = (
    *_COMMON_GEOMETRY[:8],
    _spec("fc", "f'_{c}", "Concrete compressive strength", "Characteristic concrete strength used by the creep coefficients.", "MPa", "Materials"),
    _spec("Ec", "E_c", "Concrete elastic modulus", "Concrete modulus used to convert sustained stress to creep strain.", "MPa", "Materials"),
    _spec("member_faces_exposed", "faces", "Exposed faces", "Member faces exposed for the notional-thickness and creep environment selection.", None, "Creep and shrinkage"),
    _spec("env_option", "environment", "Creep environment", "Environment used by the creep coefficient tables.", None, "Creep and shrinkage"),
    _spec("t_creep", "t", "Time after loading", "Time after loading at which the creep coefficient is evaluated.", "days", "Creep and shrinkage"),
    _spec("age_at_loading", "t_0", "Age at loading", "Concrete age when sustained loading begins.", "days", "Creep and shrinkage"),
    _spec("sustained_Mstar_kNm", "M_{sust}", "Sustained moment", "Governing sustained service moment used to resolve the sustained concrete stress.", "kNm", "Design actions"),
    _spec("sls_Mstar", "M_s", "Service bending action", "Service bending action from which the sustained moment is resolved.", "kNm", "Design actions"),
    _spec("sustained_sigma_cs_mpa", "σ_{cs}", "Sustained concrete stress", "Resolved sustained compression stress used by the creep strain calculation.", "MPa", "Resolved section parameters"),
    _spec("sustained_section_modulus_mm3", "Z_{comp}", "Compression section modulus", "Section modulus used to resolve the sustained compression stress.", "mm³", "Resolved section parameters"),
    _spec("stress_ratio", "σ_{cs}/f'_{c}", "Sustained stress ratio", "Ratio of sustained compression stress to concrete strength.", None, "Serviceability"),
    _spec("sustained_compression_fibre", "compression face", "Compression fibre", "Face in compression for the governing sustained bending action.", None, "Method / assumptions"),
    _spec("A_g", "A_g", "Gross concrete area", "Resolved gross concrete area used to calculate the notional thickness.", "mm²", "Resolved section parameters"),
    _spec("ue", "u_e", "Exposed perimeter", "Resolved exposed perimeter used to calculate the notional thickness.", "mm", "Resolved section parameters"),
    _spec("th_raw", "t_h", "Calculated notional thickness", "Notional thickness before adoption of the tabulated value.", "mm", "Resolved section parameters"),
    _spec("th_table", "t_{h,table}", "Adopted notional thickness", "Tabulated notional thickness used by the creep coefficients.", "mm", "Resolved section parameters"),
)


def _creep_page_specs() -> tuple[ReferenceSpec, ...]:
    """Metadata for the controls and resolved drivers shown on Creep."""

    keys = {
        "b",
        "D",
        "fc",
        "Ec",
        "member_faces_exposed",
        "env_option",
        "t_creep",
        "age_at_loading",
        "sustained_Mstar_kNm",
        "sls_Mstar",
        "sustained_sigma_cs_mpa",
        "sustained_section_modulus_mm3",
        "stress_ratio",
        "sustained_compression_fibre",
        "A_g",
        "ue",
        "th_raw",
        "th_table",
    }
    return _specs_for_keys(_CREEP_SPECS, keys)


def build_creep_reference(values: Mapping[str, Any]) -> PageReferenceModel:
    source = _clean_mapping(values)
    return _model(
        "creep",
        source,
        _creep_page_specs(),
        source_label=_source_label(source, "Beam Inputs"),
    )


_SHRINKAGE_SPECS = (
    *_COMMON_GEOMETRY[:8],
    _spec("fc", "f'_{c}", "Concrete compressive strength", "Characteristic concrete strength used by the shrinkage method.", "MPa", "Materials"),
    _spec("member_faces_exposed", "faces", "Exposed faces", "Member faces exposed for drying shrinkage and exposed-perimeter resolution.", None, "Creep and shrinkage"),
    _spec("shrinkage_env", "environment", "Shrinkage environment", "Environment used by the AS 3600 shrinkage table method.", None, "Creep and shrinkage"),
    _spec("shrinkage_method", "method", "Shrinkage method", "Selected AS 3600 or EC2/C766 shrinkage calculation method.", None, "Method / assumptions"),
    _spec("t_shrink", "t", "Shrinkage age", "Time since drying or shrinkage development begins.", "days", "Creep and shrinkage"),
    _spec("shrinkage_relative_humidity_percent", "RH", "Relative humidity", "Relative humidity used by the EC2/C766 shrinkage method.", "%", "Creep and shrinkage"),
    _spec("shrinkage_cement_class", "cement", "Cement class", "Cement class used by the EC2/C766 shrinkage method.", None, "Materials"),
    _spec("shrinkage_drying_start_age_days", "t_s", "Drying start age", "Age at which drying shrinkage starts.", "days", "Creep and shrinkage"),
    _spec("A_g", "A_g", "Gross concrete area", "Resolved gross concrete area used to determine notional thickness.", "mm²", "Resolved section parameters"),
    _spec("ue", "u_e", "Exposed perimeter", "Resolved exposed perimeter used for drying and notional thickness.", "mm", "Resolved section parameters"),
    _spec("th_raw", "t_h", "Calculated notional thickness", "Calculated notional thickness before adoption of the nearest table value.", "mm", "Resolved section parameters"),
    _spec("th_table", "t_{h,table}", "Adopted notional thickness", "Nearest standard notional thickness used by the table-based checks.", "mm", "Resolved section parameters"),
)


def _shrinkage_page_specs(values: Mapping[str, Any]) -> tuple[ReferenceSpec, ...]:
    """Metadata for the active method branch shown on Shrinkage."""

    keys = {
        "b",
        "D",
        "fc",
        "member_faces_exposed",
        "shrinkage_method",
        "t_shrink",
        "A_g",
        "ue",
        "th_raw",
        "th_table",
    }
    method = str(values.get("shrinkage_method") or "existing_as3600").lower()
    if method == "existing_as3600":
        keys.add("shrinkage_env")
    else:
        keys.update(
            {
                "shrinkage_relative_humidity_percent",
                "shrinkage_cement_class",
                "shrinkage_drying_start_age_days",
            }
        )
    return _specs_for_keys(_SHRINKAGE_SPECS, keys)


def build_shrinkage_reference(values: Mapping[str, Any]) -> PageReferenceModel:
    source = _clean_mapping(values)
    method_display = {
        "existing_as3600": "Existing StructuralBase method (AS 3600:2018)",
        "ec2_c766": "EC2 equation method (CIRIA C766 Appendices A3-A4)",
    }
    return _model(
        "shrinkage",
        source,
        _shrinkage_page_specs(source),
        source_label=_source_label(source, "Beam Inputs"),
        display_values={
            "shrinkage_method": method_display.get(
                str(source.get("shrinkage_method") or "").lower(),
                str(source.get("shrinkage_method") or UNAVAILABLE),
            )
        },
    )


_CRACK_SPECS = (
    *_COMMON_GEOMETRY,
    _spec("crack_control_method", "method", "Crack-control method", "Method currently selected for the Crack Control page.", None, "Method / assumptions"),
    _spec("fc", "f'_{c}", "Concrete compressive strength", "Concrete strength used by the crack-control calculation.", "MPa", "Materials"),
    _spec("fsy", "f_{sy}", "Steel yield strength", "Steel yield strength used to cap the crack-control steel stress limit.", "MPa", "Materials"),
    _spec("Ec", "E_c", "Concrete elastic modulus", "Concrete modulus used by the crack-control strain calculations.", "MPa", "Materials"),
    _spec("Es", "E_s", "Steel elastic modulus", "Steel modulus used to resolve service reinforcement stress.", "MPa", "Materials"),
    _spec("cover_mm", "c", "Tensile reinforcement cover", "Clear cover to the tensile reinforcement used by crack spacing calculations.", "mm", "Section geometry"),
    _spec("rowgap_bot", "g_{bot}", "Bottom reinforcement — Row gap", "Clear vertical gap between bottom reinforcement layers.", "mm", "Reinforcement", "Row gap"),
    _spec("exposure_class", "exposure", "Exposure class", "Exposure classification controlling crack-width criteria.", None, "Crack-control environment"),
    _spec("crack_member_type", "member", "Resultant action type", "Whether the member is treated as primarily in flexure or tension.", None, "Method / assumptions"),
    _spec("crack_tension_face", "face", "Tension face", "Tension face used when selecting the active reinforcement for a flanged section.", None, "Section geometry"),
    _spec("wmax_char_limit", "w'_{max}", "Crack-width limit", "Characteristic crack-width limit for the selected exposure and member requirements.", "mm", "Crack-control environment"),
    _spec("bar_diameter_mm", "d_b", "Tensile bar diameter", "Resolved diameter of the active tensile reinforcement.", "mm", "Reinforcement"),
    _spec("bar_spacing_mm", "s", "Tensile bar spacing", "Resolved spacing of active tensile reinforcement.", "mm", "Reinforcement"),
    _spec("Ast", "A_{st}", "Tensile steel area", "Resolved active tensile reinforcement area used by crack checks.", "mm²", "Reinforcement"),
    _spec("sigma_sr", "σ_{sr}", "Service reinforcement stress", "Service reinforcement stress used by the crack-control check.", "MPa", "Resolved section parameters"),
    _spec("crack_k1", "k_1", "Bond coefficient", "Bond coefficient used in crack-spacing calculations.", None, "Method / assumptions"),
    _spec("crack_k2", "k_2", "Strain distribution factor", "Strain-distribution factor used in crack-width calculations.", None, "Method / assumptions"),
    _spec("sls_Mstar", "M_s", "Service moment", "Service moment associated with the current crack-control action.", "kNm", "Design actions"),
    _spec("phi_cc_t", "ϕ_{cc}", "Creep coefficient", "Creep coefficient used when resolving the service strain difference.", None, "Serviceability"),
    _spec("eps_cs_total_micro", "ε_{cs}", "Total shrinkage strain", "Resolved total shrinkage strain used in the crack-control strain difference.", "με", "Serviceability"),
    _spec("crack_c766_restraint_type", "restraint", "C766 restraint type", "Restraint condition selected for the CIRIA C766/EC2 path.", None, "Crack-control environment"),
    _spec("crack_c766_t1_c", "ΔT_1", "Early temperature drop", "Early-age temperature drop used to calculate restrained strain.", "°C", "Crack-control environment"),
    _spec("crack_c766_t2_c", "ΔT_2", "Long-term temperature change", "Long-term temperature change used to calculate restrained strain.", "°C", "Crack-control environment"),
    _spec("crack_c766_alpha_micro_per_c", "α_T", "Thermal expansion coefficient", "Thermal expansion coefficient for the C766 path.", "μɛ/°C", "Materials"),
    _spec("crack_c766_restraint_early", "R_1", "Early restraint", "Early restraint factor used in the C766 strain model.", None, "Crack-control environment"),
    _spec("crack_c766_restraint_medium", "R_2", "Medium-term restraint", "Medium-term restraint factor used in the C766 strain model.", None, "Crack-control environment"),
    _spec("crack_c766_restraint_long", "R_3", "Long-term restraint", "Long-term restraint factor used in the C766 strain model.", None, "Crack-control environment"),
    _spec("crack_c766_tensile_capacity_micro", "ε_{ctu}", "Tensile strain capacity", "Tensile strain capacity used by the C766 path.", "μɛ", "Crack-control environment"),
    _spec("crack_c766_effective_reinforcement_ratio", "ρ_{p,eff}", "Effective reinforcement ratio", "Effective reinforcement ratio used by the C766 restraint model.", None, "Reinforcement"),
    _spec("crack_c766_modular_ratio", "α_e", "Effective modular ratio", "Effective modular ratio used by the C766 end-restraint equation.", None, "Method / assumptions"),
    _spec("crack_c766_non_uniform_k", "k", "Non-uniform stress coefficient", "Non-uniform stress coefficient used by the C766 end-restraint equation.", None, "Method / assumptions"),
    _spec("crack_c766_stress_distribution_kc", "k_c", "Stress-distribution coefficient", "Stress-distribution coefficient used by the C766 end-restraint equation.", None, "Method / assumptions"),
    _spec("crack_c766_characteristic_tensile_mpa", "f_{ct,eff}", "Characteristic tensile strength", "Characteristic tensile strength at cracking used by the C766 end-restraint equation.", "MPa", "Materials"),
    _spec("crack_c766_total_reinforcement_ratio", "ρ_{tot}", "Total reinforcement ratio", "Total reinforcement-to-tension-area ratio used by the C766 end-restraint equation.", None, "Reinforcement"),
    _spec("crack_c766_autogenous_early_micro", "ε_{ca,early}", "Early autogenous shrinkage", "Autogenous shrinkage supplied to the C766 general restraint path.", "με", "Crack-control environment"),
    _spec("crack_c766_autogenous_long_micro", "ε_{ca,long}", "Long-term autogenous shrinkage", "Long-term autogenous shrinkage supplied to the C766 general restraint path.", "με", "Crack-control environment"),
    _spec("crack_c766_bar_diameter_mm", "d_b", "C766 bar diameter", "Bar diameter used by the C766 path.", "mm", "Reinforcement"),
    _spec("crack_c766_cover_mm", "c", "C766 cover", "Cover used by the C766 path.", "mm", "Section geometry"),
    _spec("crack_wall_thickness_mm", "t_w", "Wall thickness", "Wall thickness used by the AS 5100.5 restrained-wall path.", "mm", "Section geometry"),
    _spec("crack_wall_horizontal_area_per_face", "A_{s,h}/face", "Wall horizontal reinforcement", "Provided horizontal wall reinforcement area per face.", "mm²/m", "Reinforcement"),
    _spec("crack_wall_vertical_spacing_mm", "s_v", "Wall vertical spacing", "Provided vertical reinforcement spacing in the wall path.", "mm", "Reinforcement"),
    _spec("crack_wall_in_base_zone", "base zone", "Wall base-zone condition", "Whether the AS 5100 wall reinforcement is being checked in the base zone.", None, "Method / assumptions"),
)


def _crack_page_specs(values: Mapping[str, Any]) -> tuple[ReferenceSpec, ...]:
    """Return only the inputs used by the selected crack-control method."""

    method = str(values.get("crack_control_method") or "existing_as3600").lower()
    if method == "as5100_wall":
        keys = {
            "crack_control_method",
            "crack_wall_thickness_mm",
            "crack_wall_horizontal_area_per_face",
            "crack_wall_vertical_spacing_mm",
            "crack_wall_in_base_zone",
        }
        return _specs_for_keys(_CRACK_SPECS, keys)

    if method == "ciria_c766_ec2":
        keys = {
            "crack_control_method",
            "crack_c766_restraint_type",
            "crack_c766_cover_mm",
            "crack_c766_bar_diameter_mm",
            "crack_c766_effective_reinforcement_ratio",
        }
        restraint = str(values.get("crack_c766_restraint_type") or "").lower()
        if restraint == "end":
            keys.update(
                {
                    "Es",
                    "crack_c766_modular_ratio",
                    "crack_c766_non_uniform_k",
                    "crack_c766_stress_distribution_kc",
                    "crack_c766_characteristic_tensile_mpa",
                    "crack_c766_total_reinforcement_ratio",
                }
            )
        else:
            keys.update(
                {
                    "crack_c766_t1_c",
                    "crack_c766_t2_c",
                    "crack_c766_alpha_micro_per_c",
                    "crack_c766_restraint_early",
                    "crack_c766_restraint_medium",
                    "crack_c766_restraint_long",
                    "crack_c766_tensile_capacity_micro",
                    "crack_c766_autogenous_early_micro",
                    "crack_c766_autogenous_long_micro",
                }
            )
        return _specs_for_keys(_CRACK_SPECS, keys)

    keys = {
        item[0]
        for item in _active_section_geometry_specs(
            values,
            include_span=False,
            include_covers=False,
        )
    }
    keys.update(
        {
            "crack_control_method",
            "fc",
            "fsy",
            "Ec",
            "Es",
            "cover_mm",
            "rowgap_bot",
            "exposure_class",
            "crack_member_type",
            "crack_tension_face",
            "wmax_char_limit",
            "bar_diameter_mm",
            "bar_spacing_mm",
            "Ast",
            "sigma_sr",
            "crack_k1",
            "crack_k2",
            "sls_Mstar",
            "phi_cc_t",
            "eps_cs_total_micro",
        }
    )
    return _specs_for_keys(_CRACK_SPECS, keys)


def build_crack_reference(values: Mapping[str, Any]) -> PageReferenceModel:
    source = _with_row_model_aliases(_clean_mapping(values))
    display_values = _reinforcement_display_values(source)
    crack_method = str(source.get("crack_control_method") or "").lower()
    display_values["crack_control_method"] = {
        "existing_as3600": "Existing StructuralBase method (AS 3600:2018)",
        "as5100_wall": "AS 5100.5:2017 restrained wall (Clause 11.7.2)",
        "ciria_c766_ec2": "CIRIA C766 + EC2 equation method",
    }.get(crack_method, str(source.get("crack_control_method") or UNAVAILABLE))
    restraint_type = source.get("crack_c766_restraint_type")
    if restraint_type is not None:
        display_values["crack_c766_restraint_type"] = str(
            restraint_type
        ).replace("_", " ").title()
    if crack_method == "existing_as3600":
        source["bot_reinforcement_notation"] = display_values[
            "bot_reinforcement_notation"
        ]
    return _model(
        "crack",
        source,
        _crack_page_specs(source)
        + (
            _active_longitudinal_row_specs(source, faces=("bot",))
            + _active_reinforcement_notation_specs(faces=("bot",))
            if str(source.get("crack_control_method") or "existing_as3600").lower()
            == "existing_as3600"
            else ()
        ),
        source_label=_source_label(source, "Beam Inputs"),
        display_values=display_values,
    )


_DEFLECTION_SPECS = (
    *_COMMON_GEOMETRY,
    _spec("fc", "f'_{c}", "Concrete compressive strength", "Concrete strength used by effective stiffness and span/depth checks.", "MPa", "Materials"),
    _spec("Ec", "E_c", "Concrete elastic modulus", "Concrete modulus used by deflection calculations.", "MPa", "Materials"),
    _spec("Ec_short", "E_{c,short}", "Short-term concrete modulus", "Short-term concrete modulus before the effective long-term adjustment.", "MPa", "Materials"),
    _spec("Eceff", "E_{c,eff}", "Effective concrete modulus", "Effective concrete modulus actually used by the current deflection calculation.", "MPa", "Materials"),
    _spec("Es", "E_s", "Steel elastic modulus", "Steel modulus used by reinforcement stress and stiffness calculations.", "MPa", "Materials"),
    _spec("d", "d", "Effective depth", "Effective depth used by reinforcement ratio and stiffness calculations.", "mm", "Resolved section parameters"),
    _spec("beff", "b_{eff}", "Effective flange width", "Effective width used by the deflection section model.", "mm", "Resolved section parameters"),
    _spec("Ast", "A_{st}", "Tension reinforcement area", "Resolved tensile reinforcement area used by effective stiffness.", "mm²", "Reinforcement"),
    _spec("Asc", "A_{sc}", "Compression reinforcement area", "Resolved compression reinforcement area used by effective stiffness.", "mm²", "Reinforcement"),
    _spec("rowgap_bot", "g_{bot}", "Bottom reinforcement — Row gap", "Clear vertical gap between bottom reinforcement layers.", "mm", "Reinforcement", "Row gap"),
    _spec("rowgap_top", "g_{top}", "Top reinforcement — Row gap", "Clear vertical gap between top reinforcement layers.", "mm", "Reinforcement", "Row gap"),
    _spec("defl_support_type", "support", "Deflection support type", "Support condition used to select the deflection coefficient.", None, "Method / assumptions"),
    _spec("defl_limit_ratio", "L/Δ", "Deflection limit ratio", "Adopted span-to-deflection limit ratio.", None, "Serviceability"),
    _spec("defl_Fdef", "F_{def}", "Effective design load", "Effective design load used by the span/depth check.", "kN/m", "Design actions"),
    _spec("defl_use_simplified_ief", "I_{ef} method", "Effective inertia method", "Whether the simplified effective-inertia method is selected.", None, "Method / assumptions"),
    _spec("defl_Ief_user", "I_{ef,user}", "User effective inertia", "User-supplied effective inertia when the simplified option is disabled.", "mm⁴", "Method / assumptions"),
    _spec("actions_source", "source", "Design actions source", "Source branch for the service actions consumed by the deflection calculation.", None, "Method / assumptions", "Design actions source"),
    _spec("beam_system_mode", "system", "Beam system mode", "Single-span or multi-span structural idealisation used by the active deflection load model.", None, "Load / analysis", "Beam system mode"),
    _spec("sls_Mstar", "M_s", "Service moment", "Service moment used by the deflection calculation.", "kNm", "Design actions"),
    _spec("sls_Vstar", "V_s", "Service shear", "Service shear associated with the current service loading.", "kN", "Design actions"),
    _spec("load_case", "case", "Loading case", "Load case used to derive the deflection shape.", None, "Load / analysis"),
    _spec("span_L_m", "L", "Analysis span", "Span used by the deflection load model.", "m", "Section geometry"),
    _spec("w_sls_kNm_per_m", "w_s", "SLS UDL", "Service uniformly distributed load used by the deflection shape.", "kN/m", "Design actions", "SLS UDL"),
    _spec("P_sls_kN", "P_s", "SLS point load", "Service point load used by the deflection shape.", "kN", "Design actions", "SLS point load"),
    _spec("a_m", "a", "Point-load location", "Location of a service point load.", "m", "Load / analysis", "Point-load location"),
    _spec("g_udl_kNm_per_m", "g", "Dead UDL", "Permanent uniformly distributed load resolved for the active deflection load model.", "kN/m", "Design actions", "Dead UDL g (kN/m)"),
    _spec("q_udl_kNm_per_m", "q", "Live UDL", "Variable uniformly distributed load resolved for the active deflection load model.", "kN/m", "Design actions", "Live UDL q (kN/m)"),
    _spec("psi_udl", "ψ_s", "Sustained factor", "Portion of the variable UDL treated as sustained for serviceability effects.", None, "Load / analysis", "Sustained factor ψ_s"),
    _spec("G_point_kN", "G", "Dead point load", "Permanent point load resolved for the active deflection load model.", "kN", "Design actions", "Dead point load G (kN)"),
    _spec("Q_point_kN", "Q", "Live point load", "Variable point load resolved for the active deflection load model.", "kN", "Design actions", "Live point load Q (kN)"),
    _spec("psi_point", "ψ_s", "Point-load sustained factor", "Portion of the variable point load treated as sustained for serviceability effects.", None, "Load / analysis", "Sustained factor ψ_s for point load"),
    _spec("defl_L_eff", "L_{eff}", "Effective deflection span", "Effective span used to derive the deflection design load.", "m", "Section geometry"),
    _spec("stress_ratio", "σ_{cs}/f'_{c}", "Sustained stress ratio", "Sustained concrete stress ratio used by long-term deflection.", None, "Serviceability"),
    _spec("sustained_Mstar_kNm", "M_{sust}", "Sustained moment", "Sustained service moment used by long-term deflection.", "kNm", "Design actions"),
    _spec("sustained_sigma_cs_mpa", "σ_{cs}", "Sustained concrete stress", "Sustained concrete stress used by long-term deflection.", "MPa", "Serviceability"),
    _spec("phi_cc_t", "φ_{cc}", "Creep coefficient", "Creep coefficient used by long-term deflection.", None, "Serviceability"),
)


def _deflection_page_specs(values: Mapping[str, Any]) -> tuple[ReferenceSpec, ...]:
    """Metadata for the active Deflection inputs and resolved drivers."""

    keys = {
        item[0]
        for item in _active_section_geometry_specs(
            values,
            include_span=True,
            include_covers=False,
        )
    }
    keys.update(
        {
            "fc",
            "Ec",
            "Ec_short",
            "Eceff",
            "Es",
            "d",
            "bw",
            "beff",
            "Ast",
            "Asc",
            "rowgap_bot",
            "rowgap_top",
            "defl_support_type",
            "defl_limit_ratio",
            "defl_Fdef",
            "defl_use_simplified_ief",
            "beam_system_mode",
            "actions_source",
            "sls_Mstar",
            "sls_Vstar",
            "load_case",
            "span_L_m",
            "defl_L_eff",
            "stress_ratio",
            "sustained_Mstar_kNm",
            "sustained_sigma_cs_mpa",
            "phi_cc_t",
        }
    )
    if not _as_bool(values.get("defl_use_simplified_ief"), default=True):
        keys.add("defl_Ief_user")

    case = str(values.get("load_case") or "").strip().lower()
    system = str(values.get("beam_system_mode") or "").strip().lower()
    show_udl = "udl" in case or (not case and "multi" not in system)
    show_point = "point" in case or "overhang" in case
    if "multi" in system or "multi" in case:
        show_udl = True
        show_point = True
    if show_udl:
        keys.update(
            {
                "w_sls_kNm_per_m",
                "g_udl_kNm_per_m",
                "q_udl_kNm_per_m",
                "psi_udl",
            }
        )
    if show_point:
        keys.update(
            {
                "P_sls_kN",
                "G_point_kN",
                "Q_point_kN",
                "psi_point",
                "a_m",
            }
        )
    return _specs_for_keys(_DEFLECTION_SPECS, keys)


def build_deflection_reference(values: Mapping[str, Any]) -> PageReferenceModel:
    source = _with_row_model_aliases(_clean_mapping(values))
    display_values = _reinforcement_display_values(source)
    source.update(
        {
            key: display_values[key]
            for key in ("bot_reinforcement_notation", "top_reinforcement_notation")
        }
    )
    actions_source = str(source.get("actions_source") or "").strip().lower()
    if "teaching" in actions_source or "load analysis" in actions_source:
        display_values["actions_source"] = "Load Analysis"
    elif actions_source:
        display_values["actions_source"] = "Beam Inputs"
    display_values["defl_use_simplified_ief"] = (
        "Simplified reinforced-member Iₑf"
        if _as_bool(source.get("defl_use_simplified_ief"), default=True)
        else "User-specified Iₑf"
    )
    return _model(
        "deflection",
        source,
        _deflection_page_specs(source)
        + _active_longitudinal_row_specs(source)
        + _active_reinforcement_notation_specs(),
        source_label=_source_label(source, "Beam Inputs"),
        display_values=display_values,
    )


PAGE_REFERENCE_BUILDERS.update(
    {
        "start": build_start_reference,
        "inputs": build_beam_inputs_reference,
        "design": build_load_analysis_reference,
        "bending": build_bending_reference,
        "shear": build_shear_reference,
        "creep": build_creep_reference,
        "shrinkage": build_shrinkage_reference,
        "crack": build_crack_reference,
        "deflection": build_deflection_reference,
    }
)


def build_page_reference_model(
    page_key: str,
    values: Mapping[str, Any] | None = None,
) -> PageReferenceModel:
    """Build a page model through the single page adapter registry."""

    try:
        builder = PAGE_REFERENCE_BUILDERS[str(page_key)]
    except KeyError as exc:
        raise ValueError(f"No page reference builder for {page_key!r}") from exc
    return builder(values or {})


def render_page_reference_sidebar(model: PageReferenceModel) -> None:
    """Render the two read-only reference folders without touching state."""

    import streamlit as st

    def is_derived_reference_item(item: PageReferenceItem) -> bool:
        """Keep derived summaries out of the input glossary.

        The compact reo notation is useful beside the live values, but it is
        not an editable page input.  Showing it in the glossary made it look
        like a second reinforcement input alongside the actual Rows/Layout/
        Bars/Spacing/Ø controls.
        """

        return item.key.endswith("_reinforcement_notation")

    def glossary_heading(item: PageReferenceItem) -> str:
        # Repeating controls need their face/layer context because the page
        # deliberately reuses short labels such as ``Rows`` and ``Bars``.
        if item.input_label in _REPEATING_REINFORCEMENT_LABELS:
            return item.name
        return item.input_label or item.name

    def current_value_label(item: PageReferenceItem) -> str:
        # Repeating controls have a short widget label (Bars, Layout, …). Use
        # their contextual metadata in the value list so bottom/top rows never
        # collapse into ambiguous duplicate labels.  Keep the exact widget
        # label in the value line as well as in the glossary.
        if item.key.endswith("_reinforcement_notation"):
            return f"{item.name} (derived)"
        if item.input_label in _REPEATING_REINFORCEMENT_LABELS:
            return item.name
        return item.input_label or item.name

    with st.sidebar.expander("Glossary of terms", expanded=False):
        visible_items = tuple(
            item
            for item in model.items
            if item.visible and not is_derived_reference_item(item)
        )
        if not visible_items:
            st.caption("No page-specific engineering inputs.")
        else:
            glossary_categories: dict[str, list[PageReferenceItem]] = defaultdict(list)
            for item in visible_items:
                glossary_categories[item.category].append(item)
            for category, items in glossary_categories.items():
                lines = [f"**{category}**"]
                for item in items:
                    units = f"  \nUnits: {item.units}" if item.units else ""
                    input_label = item.input_label or item.name
                    heading = glossary_heading(item)
                    page_label = (
                        f"Page input: `{input_label}`  \n"
                        if input_label != heading
                        else ""
                    )
                    engineering_name = (
                        f"Engineering name: {item.name}  \n"
                        if item.name != heading and item.name != input_label
                        else ""
                    )
                    lines.append(
                        f"**{heading}**  \n"
                        f"{page_label}"
                        f"{engineering_name}"
                        f"Symbol: `{item.symbol}`  \n"
                        f"{item.definition}{units}"
                    )
                st.markdown("\n\n".join(lines))

    with st.sidebar.expander("Current page values", expanded=False):
        if model.source_label:
            st.caption(f"Design source: {model.source_label}")
        visible_items = tuple(item for item in model.items if item.visible)
        if not visible_items:
            st.caption("No page-specific engineering inputs.")
        else:
            value_categories: dict[str, list[PageReferenceItem]] = defaultdict(list)
            for item in visible_items:
                value_categories[item.category].append(item)
            for category, items in value_categories.items():
                lines = [f"**{category}**"]
                for item in items:
                    value = item.display_value or _display_scalar(item.value, item.units)
                    lines.append(f"**{current_value_label(item)}** = {value}")
                st.markdown("\n\n".join(lines))


__all__ = [
    "PAGE_REFERENCE_BUILDERS",
    "PageReferenceItem",
    "PageReferenceModel",
    "build_beam_inputs_reference",
    "build_bending_reference",
    "build_crack_reference",
    "build_creep_reference",
    "build_deflection_reference",
    "build_load_analysis_reference",
    "build_page_reference_model",
    "build_shear_reference",
    "build_shrinkage_reference",
    "build_start_reference",
    "render_page_reference_sidebar",
]
