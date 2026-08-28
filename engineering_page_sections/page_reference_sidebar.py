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

    def __post_init__(self) -> None:
        for field_name in ("key", "symbol", "name", "definition", "category"):
            if not str(getattr(self, field_name) or "").strip():
                raise ValueError(f"Page reference {field_name} is required")


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


ReferenceSpec = tuple[str, str, str, str, str | None, str]


def _spec(
    key: str,
    symbol: str,
    name: str,
    definition: str,
    units: str | None,
    category: str,
) -> ReferenceSpec:
    return (key, symbol, name, definition, units, category)


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
    _spec("rowgap_bot", "g_{bot}", "Bottom row gap", "Clear vertical gap between bottom reinforcement layers.", "mm", "Reinforcement"),
    _spec("rowgap_top", "g_{top}", "Top row gap", "Clear vertical gap between top reinforcement layers.", "mm", "Reinforcement"),
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
    if units in {"mm", "mm²", "mm³", "mm⁴", "bars", "legs", "days"}:
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
    return f"{text} {units}" if units else text


def _items(
    values: Mapping[str, Any],
    specs: tuple[ReferenceSpec, ...],
    *,
    display_values: Mapping[str, str] | None = None,
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
        )
        for key, symbol, name, definition, units, category in specs
    )


def _model(
    page_key: str,
    values: Mapping[str, Any],
    specs: tuple[ReferenceSpec, ...],
    *,
    source_label: str | None = None,
    display_values: Mapping[str, str] | None = None,
) -> PageReferenceModel:
    return PageReferenceModel(
        page_key=page_key,
        items=_items(values, specs, display_values=display_values),
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
            known[item[0]] = item
    if key in known:
        return known[key]

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

    # Repeating longitudinal reinforcement rows.
    row_match = re.match(r"^(bot|top)_row_(\d+)_(mode|bars|spacing|dia)$", key)
    if row_match:
        face, row, field = row_match.groups()
        face_label = "bottom" if face == "bot" else "top"
        if field == "mode":
            return _spec(
                key,
                f"layout_{{{face},{row}}}",
                f"{face_label.title()} row {row} layout",
                f"Whether {face_label} longitudinal reinforcement row {row} is specified by bar count or spacing.",
                None,
                "Reinforcement",
            )
        if field == "bars":
            return _spec(
                key,
                f"n_{{{face},{row}}}",
                f"{face_label.title()} row {row} bar count",
                f"Number of bars in {face_label} longitudinal reinforcement row {row}.",
                "bars",
                "Reinforcement",
            )
        if field == "spacing":
            return _spec(
                key,
                f"s_{{{face},{row}}}",
                f"{face_label.title()} row {row} spacing",
                f"Centre-to-centre spacing of {face_label} longitudinal reinforcement row {row}.",
                "mm",
                "Reinforcement",
            )
        return _spec(
            key,
            f"d_{{b,{face},{row}}}",
            f"{face_label.title()} row {row} bar diameter",
            f"Nominal diameter of {face_label} longitudinal reinforcement row {row}.",
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


def build_beam_inputs_reference(values: Mapping[str, Any]) -> PageReferenceModel:
    from state_and_helpers import BEAM_PROJECT_PARAM_KEYS

    source = _clean_mapping(values)
    specs = tuple(_parameter_spec(str(key)) for key in BEAM_PROJECT_PARAM_KEYS)
    return _model(
        "inputs",
        source,
        specs,
        source_label=str(source.get("reference_source") or "Beam Inputs"),
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


def build_load_analysis_reference(values: Mapping[str, Any]) -> PageReferenceModel:
    source = _clean_mapping(values)
    static_keys = {item[0] for item in _LOAD_ANALYSIS_SPECS}
    dynamic_specs = tuple(
        _parameter_spec(str(key))
        for key in sorted(source)
        if str(key).startswith(
            (
                "design_point_",
                "design_ms_",
                "design_",
                "load_",
                "sfd_",
            )
        )
        and str(key) not in static_keys
        and str(key) != "reference_source"
    )
    return _model(
        "design",
        source,
        _LOAD_ANALYSIS_SPECS + dynamic_specs,
        source_label="Load Analysis",
    )


_BENDING_SPECS = (
    *_COMMON_GEOMETRY,
    *_COMMON_MATERIALS,
    *_BENDING_REINFORCEMENT,
    _spec("d", "d", "Effective depth", "Distance from the compression face to the centroid of the tensile reinforcement.", "mm", "Resolved section parameters"),
    _spec("do", "d_o", "Compression reinforcement depth", "Distance from the compression face to the centroid of the compression reinforcement.", "mm", "Resolved section parameters"),
    _spec("Ast_bot", "A_{st,bot}", "Bottom tensile steel area", "Resolved area of bottom longitudinal reinforcement used by the bending page.", "mm²", "Resolved section parameters"),
    _spec("Ast_top", "A_{st,top}", "Top reinforcement area", "Resolved area of top longitudinal reinforcement used by the bending page.", "mm²", "Resolved section parameters"),
    _spec("M_star", "M^*", "Current ULS moment", "ULS moment for the currently selected sagging or hogging detail view.", "kNm", "Design actions"),
    _spec("M_s", "M_s", "Current SLS moment", "SLS moment for the currently selected bending detail view.", "kNm", "Design actions"),
    _spec("moment_sign", "sign", "Moment sign", "Sagging or hogging detail view controlling compression and tension faces.", None, "Method / assumptions"),
    _spec("actions_mode", "actions", "Action source mode", "Whether actions are manually specified or resolved from Load Analysis.", None, "Method / assumptions"),
    _spec("sls_ignore_compression_reinforcement", "SLS C_s", "SLS compression reinforcement option", "Whether compression-side reinforcement is excluded from the cracked SLS section projection.", None, "Method / assumptions"),
    _spec("phi_bend", "φ", "Bending strength reduction factor", "Strength reduction factor used by the ULS bending capacity check.", None, "Method / assumptions"),
)


def build_bending_reference(values: Mapping[str, Any]) -> PageReferenceModel:
    source = _clean_mapping(values)
    return _model(
        "bending",
        source,
        _BENDING_SPECS,
        source_label=_source_label(source, "Beam Inputs"),
        display_values={
            "sls_ignore_compression_reinforcement": (
                "Excluded"
                if bool(source.get("sls_ignore_compression_reinforcement"))
                else "Included"
            )
        },
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
    _spec("k_d_option", "k_d", "Duct reduction option", "Selected duct condition used to resolve the web duct factor.", None, "Method / assumptions"),
    _spec("b_v", "b_v", "Effective web width", "Resolved effective web width used by shear capacity equations.", "mm", "Resolved shear parameters"),
    _spec("d_v", "d_v", "Effective shear depth", "Resolved effective shear depth used by shear capacity equations.", "mm", "Resolved shear parameters"),
    _spec("V_eq", "V^*_{eq}", "Equivalent shear action", "Combined shear action including the torsion-equivalent contribution.", "kN", "Resolved shear parameters"),
    _spec("eps_x", "ε_x", "Longitudinal strain", "Longitudinal strain used by the MCFT shear method.", None, "Resolved shear parameters"),
    _spec("k_v", "k_v", "MCFT shear factor", "Resolved shear strength factor from the selected shear method.", None, "Resolved shear parameters"),
    _spec("theta_v_deg", "θ_v", "Compression strut angle", "Resolved compression-strut angle used by the MCFT equations.", "°", "Resolved shear parameters"),
    _spec("crack_theta_deg", "θ", "Reference crack angle", "Reference crack angle used by the torsion screening convention.", "°", "Method / assumptions"),
    _spec("shear_auto_design", "auto", "Automatic shear design", "Whether the existing automatic shear-detailing mode is enabled.", None, "Method / assumptions"),
    _spec("actions_mode", "actions", "Action source mode", "Whether current actions are manual or Load Analysis driven.", None, "Method / assumptions"),
)


def build_shear_reference(values: Mapping[str, Any]) -> PageReferenceModel:
    source = _clean_mapping(values)
    return _model(
        "shear",
        source,
        _SHEAR_SPECS,
        source_label=_source_label(source, "Beam Inputs"),
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


def build_creep_reference(values: Mapping[str, Any]) -> PageReferenceModel:
    source = _clean_mapping(values)
    return _model(
        "creep",
        source,
        _CREEP_SPECS,
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


def build_shrinkage_reference(values: Mapping[str, Any]) -> PageReferenceModel:
    source = _clean_mapping(values)
    return _model(
        "shrinkage",
        source,
        _SHRINKAGE_SPECS,
        source_label=_source_label(source, "Beam Inputs"),
    )


_CRACK_SPECS = (
    *_COMMON_GEOMETRY[:8],
    _spec("crack_control_method", "method", "Crack-control method", "Method currently selected for the Crack Control page.", None, "Method / assumptions"),
    _spec("fc", "f'_{c}", "Concrete compressive strength", "Concrete strength used by the crack-control calculation.", "MPa", "Materials"),
    _spec("fsy", "f_{sy}", "Steel yield strength", "Steel yield strength used to cap the crack-control steel stress limit.", "MPa", "Materials"),
    _spec("Ec", "E_c", "Concrete elastic modulus", "Concrete modulus used by the crack-control strain calculations.", "MPa", "Materials"),
    _spec("Es", "E_s", "Steel elastic modulus", "Steel modulus used to resolve service reinforcement stress.", "MPa", "Materials"),
    _spec("cover_mm", "c", "Tensile reinforcement cover", "Clear cover to the tensile reinforcement used by crack spacing calculations.", "mm", "Section geometry"),
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


def build_crack_reference(values: Mapping[str, Any]) -> PageReferenceModel:
    source = _clean_mapping(values)
    return _model(
        "crack",
        source,
        _CRACK_SPECS,
        source_label=_source_label(source, "Beam Inputs"),
    )


_DEFLECTION_SPECS = (
    *_COMMON_GEOMETRY[:6],
    _spec("fc", "f'_{c}", "Concrete compressive strength", "Concrete strength used by effective stiffness and span/depth checks.", "MPa", "Materials"),
    _spec("Ec", "E_c", "Concrete elastic modulus", "Concrete modulus used by deflection calculations.", "MPa", "Materials"),
    _spec("Ec_short", "E_{c,short}", "Short-term concrete modulus", "Short-term concrete modulus before the effective long-term adjustment.", "MPa", "Materials"),
    _spec("Eceff", "E_{c,eff}", "Effective concrete modulus", "Effective concrete modulus actually used by the current deflection calculation.", "MPa", "Materials"),
    _spec("Es", "E_s", "Steel elastic modulus", "Steel modulus used by reinforcement stress and stiffness calculations.", "MPa", "Materials"),
    _spec("d", "d", "Effective depth", "Effective depth used by reinforcement ratio and stiffness calculations.", "mm", "Resolved section parameters"),
    _spec("bw", "b_w", "Effective web width", "Web width used by the deflection section model.", "mm", "Resolved section parameters"),
    _spec("beff", "b_{eff}", "Effective flange width", "Effective width used by the deflection section model.", "mm", "Resolved section parameters"),
    _spec("Ast", "A_{st}", "Tension reinforcement area", "Resolved tensile reinforcement area used by effective stiffness.", "mm²", "Reinforcement"),
    _spec("Asc", "A_{sc}", "Compression reinforcement area", "Resolved compression reinforcement area used by effective stiffness.", "mm²", "Reinforcement"),
    _spec("nb_or_s_bot_1", "n/s_{bot,1}", "Bottom layer 1 layout", "Bottom reinforcement layout consumed by the deflection section projection.", None, "Reinforcement"),
    _spec("db_bot_1", "d_{b,bot,1}", "Bottom layer 1 bar diameter", "Bottom bar diameter consumed by the deflection section projection.", "mm", "Reinforcement"),
    _spec("nb_or_s_top_1", "n/s_{top,1}", "Top layer 1 layout", "Top reinforcement layout consumed by the deflection section projection.", None, "Reinforcement"),
    _spec("db_top_1", "d_{b,top,1}", "Top layer 1 bar diameter", "Top bar diameter consumed by the deflection section projection.", "mm", "Reinforcement"),
    _spec("rowgap_bot", "g_{bot}", "Bottom row gap", "Clear vertical gap between bottom reinforcement layers.", "mm", "Reinforcement"),
    _spec("rowgap_top", "g_{top}", "Top row gap", "Clear vertical gap between top reinforcement layers.", "mm", "Reinforcement"),
    _spec("defl_support_type", "support", "Deflection support type", "Support condition used to select the deflection coefficient.", None, "Method / assumptions"),
    _spec("defl_limit_ratio", "L/Δ", "Deflection limit ratio", "Adopted span-to-deflection limit ratio.", None, "Serviceability"),
    _spec("defl_Fdef", "F_{def}", "Effective design load", "Effective design load used by the span/depth check.", "kN/m", "Design actions"),
    _spec("defl_use_simplified_ief", "I_{ef} method", "Effective inertia method", "Whether the simplified effective-inertia method is selected.", None, "Method / assumptions"),
    _spec("defl_Ief_user", "I_{ef,user}", "User effective inertia", "User-supplied effective inertia when the simplified option is disabled.", "mm⁴", "Method / assumptions"),
    _spec("sls_Mstar", "M_s", "Service moment", "Service moment used by the deflection calculation.", "kNm", "Design actions"),
    _spec("sls_Vstar", "V_s", "Service shear", "Service shear associated with the current service loading.", "kN", "Design actions"),
    _spec("load_case", "case", "Loading case", "Load case used to derive the deflection shape.", None, "Load / analysis"),
    _spec("span_L_m", "L", "Analysis span", "Span used by the deflection load model.", "m", "Section geometry"),
    _spec("w_sls_kNm_per_m", "w_s", "SLS UDL", "Service uniformly distributed load used by the deflection shape.", "kN/m", "Design actions"),
    _spec("P_sls_kN", "P_s", "SLS point load", "Service point load used by the deflection shape.", "kN", "Design actions"),
    _spec("a_m", "a", "Point-load location", "Location of a service point load.", "m", "Load / analysis"),
    _spec("defl_L_eff", "L_{eff}", "Effective deflection span", "Effective span used to derive the deflection design load.", "m", "Section geometry"),
    _spec("stress_ratio", "σ_{cs}/f'_{c}", "Sustained stress ratio", "Sustained concrete stress ratio used by long-term deflection.", None, "Serviceability"),
    _spec("sustained_Mstar_kNm", "M_{sust}", "Sustained moment", "Sustained service moment used by long-term deflection.", "kNm", "Design actions"),
    _spec("sustained_sigma_cs_mpa", "σ_{cs}", "Sustained concrete stress", "Sustained concrete stress used by long-term deflection.", "MPa", "Serviceability"),
    _spec("phi_cc_t", "φ_{cc}", "Creep coefficient", "Creep coefficient used by long-term deflection.", None, "Serviceability"),
)


def build_deflection_reference(values: Mapping[str, Any]) -> PageReferenceModel:
    source = _clean_mapping(values)
    return _model(
        "deflection",
        source,
        _DEFLECTION_SPECS,
        source_label=_source_label(source, "Beam Inputs"),
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

    with st.sidebar.expander("Glossary of terms", expanded=False):
        if not model.items:
            st.caption("No page-specific engineering inputs.")
        else:
            glossary_categories: dict[str, list[PageReferenceItem]] = defaultdict(list)
            for item in model.items:
                glossary_categories[item.category].append(item)
            for category, items in glossary_categories.items():
                lines = [f"**{category}**"]
                for item in items:
                    units = f"  \nUnits: {item.units}" if item.units else ""
                    lines.append(
                        f"**{item.symbol} — {item.name}**  \n"
                        f"{item.definition}{units}"
                    )
                st.markdown("\n\n".join(lines))

    with st.sidebar.expander("Current page values", expanded=False):
        if model.source_label:
            st.caption(f"Design source: {model.source_label}")
        if not model.items:
            st.caption("No page-specific engineering inputs.")
        else:
            value_categories: dict[str, list[PageReferenceItem]] = defaultdict(list)
            for item in model.items:
                value_categories[item.category].append(item)
            for category, items in value_categories.items():
                lines = [f"**{category}**"]
                for item in items:
                    value = item.display_value or _display_scalar(item.value, item.units)
                    lines.append(f"**{item.symbol}** = {value}")
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
