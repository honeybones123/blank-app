from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import Any

from .contracts import ALLOWED_WIDGET_GROUPS, ALLOWED_WIDGET_KINDS, WIDGET_DISPLAY_HASH_FIELDS
from .models import InputsWidgetGroupViewModel, InputsWidgetSpecViewModel


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, tuple):
        return list(value)
    return str(value)


def stable_inputs_widget_json(payload: Any) -> str:
    return json.dumps(payload, default=_json_default, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_inputs_widget_hash(payload: Any) -> str:
    return hashlib.sha256(stable_inputs_widget_json(payload).encode("utf-8")).hexdigest()


def _tuple_options(options: Any) -> tuple[Any, ...]:
    if options is None:
        return ()
    if isinstance(options, tuple):
        return options
    if isinstance(options, list):
        return tuple(options)
    return (options,)


def _spec_from_payload(payload: dict[str, Any], *, group_id: str) -> InputsWidgetSpecViewModel:
    widget_group = str(payload.get("group_id") or group_id or "").strip()
    kind = str(payload.get("kind") or "").strip()
    if widget_group not in ALLOWED_WIDGET_GROUPS:
        raise ValueError(f"Unsupported Inputs widget group: {widget_group!r}")
    if kind not in ALLOWED_WIDGET_KINDS:
        raise ValueError(f"Unsupported Inputs widget kind: {kind!r}")
    model_payload = {
        "widget_id": str(payload.get("widget_id") or payload.get("widget_key") or "").strip(),
        "group_id": widget_group,
        "kind": kind,
        "label": str(payload.get("label") or "").strip(),
        "widget_key": str(payload.get("widget_key") or "").strip(),
        "shared_key": str(payload.get("shared_key") or "").strip(),
        "callback_key": str(payload.get("callback_key") or "").strip(),
        "help_text": str(payload.get("help_text") or "").strip(),
        "default": payload.get("default"),
        "options": _tuple_options(payload.get("options")),
        "disabled": bool(payload.get("disabled", False)),
    }
    return InputsWidgetSpecViewModel(
        **model_payload,
        display_hash=stable_inputs_widget_hash(
            {field: model_payload.get(field) for field in WIDGET_DISPLAY_HASH_FIELDS}
        ),
    )


def build_inputs_widget_group_view_model(
    *,
    group_id: str,
    widgets: Any,
) -> InputsWidgetGroupViewModel:
    group = str(group_id or "").strip()
    if group not in ALLOWED_WIDGET_GROUPS:
        raise ValueError(f"Unsupported Inputs widget group: {group!r}")
    models = tuple(
        _spec_from_payload(dict(widget), group_id=group)
        for widget in list(widgets or ())
        if isinstance(widget, dict)
    )
    return InputsWidgetGroupViewModel(
        group_id=group,
        widgets=models,
        display_hash=stable_inputs_widget_hash(
            {
                "group_id": group,
                "widgets": tuple(widget.display_hash for widget in models),
            }
        ),
    )


def build_materials_basic_widget_payloads(
    *,
    fsy_widget_key: str,
    fc_widget_key: str,
    fsy_value: Any,
    fc_value: Any,
) -> tuple[dict[str, Any], ...]:
    """Return metadata payloads for the existing Materials widgets.

    This builds metadata only. It does not render Streamlit widgets, mutate
    session state, or execute callbacks.
    """
    fsy_key = str(fsy_widget_key or "").strip()
    fc_key = str(fc_widget_key or "").strip()
    return (
        {
            "widget_id": fsy_key,
            "group_id": "materials_basic",
            "kind": "number_input",
            "label": "Steel MPa",
            "widget_key": fsy_key,
            "shared_key": "fsy",
            "callback_key": fsy_key,
            "help_text": "Yield strength of reinforcement (fsy).",
            "default": fsy_value,
        },
        {
            "widget_id": fc_key,
            "group_id": "materials_basic",
            "kind": "number_input",
            "label": "Concrete MPa",
            "widget_key": fc_key,
            "shared_key": "fc",
            "callback_key": fc_key,
            "help_text": "Characteristic compressive strength of concrete (f'c).",
            "default": fc_value,
        },
    )


def build_geometry_basic_widget_payloads(
    *,
    section_shape: str,
    current_section_shape: Any,
    shape_options: Any,
    depth_value: Any,
    span_value: Any,
    width_value: Any = None,
    flange_width_value: Any = None,
    flange_thickness_value: Any = None,
    web_width_value: Any = None,
    web_thickness_value: Any = None,
    side_cover_value: Any = None,
    detailed_mode: bool = False,
) -> tuple[dict[str, Any], ...]:
    """Return metadata payloads for the existing Geometry widgets."""
    sec_shape = str(section_shape or "").strip().upper()
    payloads: list[dict[str, Any]] = [
        {
            "widget_id": "inputs_sec_shape",
            "group_id": "geometry_basic",
            "kind": "selectbox",
            "label": "Section shape",
            "widget_key": "inputs_sec_shape",
            "shared_key": "sec_shape",
            "callback_key": "inputs_sec_shape",
            "help_text": "Select section type. Geometry inputs below update based on this selection.",
            "default": str(current_section_shape),
            "options": list(shape_options or ()),
        },
        {
            "widget_id": "inputs_D",
            "group_id": "geometry_basic",
            "kind": "number_input",
            "label": "Depth D (mm)",
            "widget_key": "inputs_D",
            "shared_key": "D",
            "callback_key": "inputs_D",
            "help_text": "Overall section depth from compression face to soffit.",
            "default": float(depth_value),
        },
        {
            "widget_id": "inputs_L",
            "group_id": "geometry_basic",
            "kind": "number_input",
            "label": "Span L (mm)",
            "widget_key": "inputs_L",
            "shared_key": "L",
            "callback_key": "inputs_L",
            "help_text": "Clear span used for deflection checks.",
            "default": float(span_value),
        },
    ]
    if sec_shape == "RECT":
        payloads.append(
            {
                "widget_id": "inputs_b",
                "group_id": "geometry_basic",
                "kind": "number_input",
                "label": "Width b (mm)",
                "widget_key": "inputs_b",
                "shared_key": "b",
                "callback_key": "inputs_b",
                "help_text": "Rectangular section width.",
                "default": float(width_value),
            }
        )
    elif sec_shape == "T":
        payloads.extend(
            [
                {
                    "widget_id": "inputs_bf",
                    "group_id": "geometry_basic",
                    "kind": "number_input",
                    "label": "Flange width bf (mm)",
                    "widget_key": "inputs_bf",
                    "shared_key": "bf",
                    "callback_key": "inputs_bf",
                    "default": float(flange_width_value),
                },
                {
                    "widget_id": "inputs_tf",
                    "group_id": "geometry_basic",
                    "kind": "number_input",
                    "label": "Flange thickness tf (mm)",
                    "widget_key": "inputs_tf",
                    "shared_key": "tf",
                    "callback_key": "inputs_tf",
                    "default": float(flange_thickness_value),
                },
                {
                    "widget_id": "inputs_bw",
                    "group_id": "geometry_basic",
                    "kind": "number_input",
                    "label": "Web width bw (mm)",
                    "widget_key": "inputs_bw",
                    "shared_key": "bw",
                    "callback_key": "inputs_bw",
                    "help_text": "Stem/web width for T section.",
                    "default": float(web_width_value),
                },
            ]
        )
    elif sec_shape == "I":
        payloads.extend(
            [
                {
                    "widget_id": "inputs_bf",
                    "group_id": "geometry_basic",
                    "kind": "number_input",
                    "label": "Top flange width bf (mm)",
                    "widget_key": "inputs_bf",
                    "shared_key": "bf",
                    "callback_key": "inputs_bf",
                    "default": float(flange_width_value),
                },
                {
                    "widget_id": "inputs_tf",
                    "group_id": "geometry_basic",
                    "kind": "number_input",
                    "label": "Top flange thickness tf (mm)",
                    "widget_key": "inputs_tf",
                    "shared_key": "tf",
                    "callback_key": "inputs_tf",
                    "default": float(flange_thickness_value),
                },
                {
                    "widget_id": "inputs_tw",
                    "group_id": "geometry_basic",
                    "kind": "number_input",
                    "label": "Web thickness tw (mm)",
                    "widget_key": "inputs_tw",
                    "shared_key": "tw",
                    "callback_key": "inputs_tw",
                    "default": float(web_thickness_value),
                },
            ]
        )
    if detailed_mode:
        payloads.append(
            {
                "widget_id": "inputs_cover_side",
                "group_id": "geometry_basic",
                "kind": "number_input",
                "label": "Side cover (mm)",
                "widget_key": "inputs_cover_side",
                "shared_key": "cover_side",
                "callback_key": "inputs_cover_side",
                "help_text": "Clear side cover to longitudinal reinforcement and ducts.",
                "default": float(side_cover_value),
            }
        )
    return tuple(payloads)


def build_shear_reinforcement_basic_widget_payloads(
    *,
    link_diameter_widget_key: str,
    link_legs_widget_key: str,
    link_spacing_widget_key: str,
    link_diameter_label: str,
    reo_bar_diameters: Any,
    link_diameter_value: Any,
    link_legs_value: Any,
    link_spacing_value: Any,
) -> tuple[dict[str, Any], ...]:
    """Return metadata payloads for the existing Shear reinforcement widgets."""
    from inputs_application.shear_state_normalization import SUPPORTED_SHEAR_LEG_COUNTS

    diameters = list(reo_bar_diameters or ())
    return (
        {
            "widget_id": str(link_diameter_widget_key),
            "group_id": "shear_reinforcement_basic",
            "kind": "selectbox",
            "label": str(link_diameter_label),
            "widget_key": str(link_diameter_widget_key),
            "shared_key": "lig_d",
            "callback_key": str(link_diameter_widget_key),
            "help_text": "Nominal diameter of shear reinforcement links (mm).",
            "default": int(link_diameter_value),
            "options": {0: "0 (off)"} | {dia: str(dia) for dia in diameters},
        },
        {
            "widget_id": str(link_legs_widget_key),
            "group_id": "shear_reinforcement_basic",
            "kind": "selectbox",
            "label": "No. of legs",
            "widget_key": str(link_legs_widget_key),
            "shared_key": "lig_legs",
            "callback_key": str(link_legs_widget_key),
            "help_text": "Number of effective legs per supported shear-link arrangement. Use 0 for no links.",
            "default": int(link_legs_value),
            "options": [0, *SUPPORTED_SHEAR_LEG_COUNTS],
        },
        {
            "widget_id": str(link_spacing_widget_key),
            "group_id": "shear_reinforcement_basic",
            "kind": "number_input",
            "label": "Link spacing (mm)",
            "widget_key": str(link_spacing_widget_key),
            "shared_key": "s_lig",
            "callback_key": str(link_spacing_widget_key),
            "help_text": "Centre-to-centre spacing of shear links along the member (mm).",
            "default": float(link_spacing_value),
        },
    )


def build_design_action_numbers_widget_payloads(
    *,
    rendered_specs: Any,
    current_values: Any,
    design_controls_enabled: bool,
) -> tuple[dict[str, Any], ...]:
    """Return metadata payloads for the rendered design action number widgets."""
    values = dict(current_values or {})
    payloads: list[dict[str, Any]] = []
    for raw_spec in list(rendered_specs or ()):
        if not isinstance(raw_spec, dict):
            continue
        widget_key = str(raw_spec.get("widget_key") or "").strip()
        if not widget_key:
            continue
        payloads.append(
            {
                "widget_id": widget_key,
                "group_id": "design_action_numbers",
                "kind": "number_input",
                "label": str(raw_spec.get("label") or ""),
                "widget_key": widget_key,
                "shared_key": str(raw_spec.get("shared_key") or ""),
                "callback_key": widget_key,
                "help_text": str(raw_spec.get("help_text") or ""),
                "default": float(values.get(widget_key, 0.0) or 0.0),
                "disabled": bool(raw_spec.get("disabled_in_design_mode")) and bool(design_controls_enabled),
            }
        )
    return tuple(payloads)


def build_time_dependent_basic_widget_payloads(
    *,
    shrinkage_time_value: Any,
    creep_time_value: Any,
    age_at_loading_value: Any,
) -> tuple[dict[str, Any], ...]:
    """Return metadata payloads for the existing time-dependent widgets."""
    return (
        {
            "widget_id": "inputs_t_shrink",
            "group_id": "time_dependent_basic",
            "kind": "number_input",
            "label": "Shrinkage time t (days)",
            "widget_key": "inputs_t_shrink",
            "shared_key": "t_shrink",
            "callback_key": "inputs_t_shrink",
            "help_text": "Time since commencement of drying (days).",
            "default": float(shrinkage_time_value),
        },
        {
            "widget_id": "inputs_t_creep",
            "group_id": "time_dependent_basic",
            "kind": "number_input",
            "label": "Creep time t (days)",
            "widget_key": "inputs_t_creep",
            "shared_key": "t_creep",
            "callback_key": "inputs_t_creep",
            "help_text": "Time after loading (days).",
            "default": float(creep_time_value),
        },
        {
            "widget_id": "inputs_age_at_loading",
            "group_id": "time_dependent_basic",
            "kind": "number_input",
            "label": "Age at loading (days)",
            "widget_key": "inputs_age_at_loading",
            "shared_key": "age_at_loading",
            "callback_key": "inputs_age_at_loading",
            "help_text": "Age of concrete at loading (days).",
            "default": float(age_at_loading_value),
        },
    )


def build_ducts_prestress_voids_basic_widget_payloads(
    *,
    ducts_count_value: Any,
    duct_diameter_value: Any,
    k_d_widget_key: str,
    k_d_value: Any,
    k_d_options: Any,
) -> tuple[dict[str, Any], ...]:
    """Return metadata payloads for the existing ducts/prestress voids widgets."""
    k_d_key = str(k_d_widget_key or "").strip()
    return (
        {
            "widget_id": "inputs_n_ducts",
            "group_id": "ducts_prestress_voids_basic",
            "kind": "number_input",
            "label": "Number of ducts crossing web",
            "widget_key": "inputs_n_ducts",
            "shared_key": "n_ducts",
            "callback_key": "inputs_n_ducts",
            "help_text": "Number of ducts/voids crossing the web (set 0 for none).",
            "default": float(ducts_count_value),
        },
        {
            "widget_id": "inputs_duct_dia",
            "group_id": "ducts_prestress_voids_basic",
            "kind": "number_input",
            "label": "Duct diameter (mm)",
            "widget_key": "inputs_duct_dia",
            "shared_key": "duct_dia",
            "callback_key": "inputs_duct_dia",
            "help_text": "Nominal duct/void diameter (mm).",
            "default": float(duct_diameter_value),
        },
        {
            "widget_id": k_d_key,
            "group_id": "ducts_prestress_voids_basic",
            "kind": "selectbox",
            "label": "k_d factor for prestressing ducts",
            "widget_key": k_d_key,
            "shared_key": "k_d_option",
            "callback_key": k_d_key,
            "help_text": "Select whether ducts are present in the web (affects k_d factor).",
            "default": k_d_value,
            "options": k_d_options,
        },
    )


def build_crack_control_inputs_basic_widget_payloads(
    *,
    exposure_class_value: Any,
    exposure_class_options: Any,
    member_type_value: Any,
    member_type_options: Any,
    k1_value: Any,
    k1_options: Any,
    k2_value: Any,
) -> tuple[dict[str, Any], ...]:
    """Return metadata payloads for the existing crack-control input widgets."""
    return (
        {
            "widget_id": "inputs_exposure_class",
            "group_id": "crack_control_inputs_basic",
            "kind": "selectbox",
            "label": "Exposure class",
            "widget_key": "inputs_exposure_class",
            "shared_key": "exposure_class",
            "callback_key": "inputs_exposure_class",
            "help_text": "Exposure classification to AS 3600.",
            "default": exposure_class_value,
            "options": exposure_class_options,
        },
        {
            "widget_id": "inputs_crack_member_type",
            "group_id": "crack_control_inputs_basic",
            "kind": "selectbox",
            "label": "Resultant action",
            "widget_key": "inputs_crack_member_type",
            "shared_key": "crack_member_type",
            "callback_key": "inputs_crack_member_type",
            "help_text": "Affects default strain distribution settings for crack-control checks.",
            "default": member_type_value,
            "options": member_type_options,
        },
        {
            "widget_id": "inputs_crack_k1",
            "group_id": "crack_control_inputs_basic",
            "kind": "selectbox",
            "label": "k1",
            "widget_key": "inputs_crack_k1",
            "shared_key": "crack_k1",
            "callback_key": "inputs_crack_k1",
            "help_text": "0.8 for deformed bars, 1.6 for plain bars.",
            "default": k1_value,
            "options": k1_options,
        },
        {
            "widget_id": "inputs_crack_k2",
            "group_id": "crack_control_inputs_basic",
            "kind": "number_input",
            "label": "k2",
            "widget_key": "inputs_crack_k2",
            "shared_key": "crack_k2",
            "callback_key": "inputs_crack_k2",
            "help_text": "Default 0.5 for flexure, 1.0 for tension. Adjust only if using a different assumed strain distribution.",
            "default": float(k2_value),
        },
    )


def build_serviceability_environment_basic_widget_payloads(
    *,
    member_faces_widget_key: Any,
    member_faces_value: Any,
    member_faces_options: Any,
    shrinkage_environment_widget_key: Any,
    shrinkage_environment_value: Any,
    shrinkage_environment_options: Any,
    creep_environment_widget_key: Any,
    creep_environment_value: Any,
    creep_environment_options: Any,
) -> tuple[dict[str, Any], ...]:
    """Return metadata payloads for the existing serviceability environment widgets."""
    return (
        {
            "widget_id": str(member_faces_widget_key),
            "group_id": "serviceability_environment_basic",
            "kind": "selectbox",
            "label": "Member / faces exposed",
            "widget_key": str(member_faces_widget_key),
            "shared_key": "member_faces_exposed",
            "callback_key": str(member_faces_widget_key),
            "help_text": "Number of faces exposed to drying environment (affects shrinkage calculations).",
            "default": member_faces_value,
            "options": list(member_faces_options or ()),
        },
        {
            "widget_id": str(shrinkage_environment_widget_key),
            "group_id": "serviceability_environment_basic",
            "kind": "selectbox",
            "label": "Shrinkage environment (Table 3.1.7.2)",
            "widget_key": str(shrinkage_environment_widget_key),
            "shared_key": "shrinkage_env",
            "callback_key": str(shrinkage_environment_widget_key),
            "help_text": "Shrinkage environment classification per AS 3600 Table 3.1.7.2.",
            "default": shrinkage_environment_value,
            "options": list(shrinkage_environment_options or ()),
        },
        {
            "widget_id": str(creep_environment_widget_key),
            "group_id": "serviceability_environment_basic",
            "kind": "selectbox",
            "label": "Creep environment (Tables 3.1.8.2 & 3.1.8.3)",
            "widget_key": str(creep_environment_widget_key),
            "shared_key": "env_option",
            "callback_key": str(creep_environment_widget_key),
            "help_text": "Creep environment classification per AS 3600 Tables 3.1.8.2 & 3.1.8.3.",
            "default": creep_environment_value,
            "options": list(creep_environment_options or ()),
        },
    )


def build_support_deflection_basic_widget_payloads(
    *,
    support_widget_key: Any,
    support_value: Any,
    support_options: Any,
    deflection_limit_widget_key: Any,
    deflection_limit_value: Any,
    deflection_limit_options: Any,
    support_disabled: Any,
    deflection_limit_help_text: str,
) -> tuple[dict[str, Any], ...]:
    """Return metadata payloads for the existing support/deflection widgets."""
    return (
        {
            "widget_id": str(support_widget_key),
            "group_id": "support_deflection_basic",
            "kind": "selectbox",
            "label": "Support condition",
            "widget_key": str(support_widget_key),
            "shared_key": "defl_support_type",
            "callback_key": str(support_widget_key),
            "help_text": "Support condition determines the deflection coefficient used in AS 3600 deflection calculations.",
            "default": support_value,
            "options": list(support_options or ()),
            "disabled": bool(support_disabled),
        },
        {
            "widget_id": str(deflection_limit_widget_key),
            "group_id": "support_deflection_basic",
            "kind": "selectbox",
            "label": "Deflection limit",
            "widget_key": str(deflection_limit_widget_key),
            "shared_key": "defl_limit_ratio",
            "callback_key": str(deflection_limit_widget_key),
            "help_text": str(deflection_limit_help_text or ""),
            "default": deflection_limit_value,
            "options": list(deflection_limit_options or ()),
        },
    )


def build_shear_section_parameters_basic_widget_payloads(
    *,
    aggregate_size_widget_key: Any,
    aggregate_size_value: Any,
    k_v_method_widget_key: Any,
    k_v_method_value: Any,
    k_v_method_options: Any,
) -> tuple[dict[str, Any], ...]:
    """Return metadata payloads for the existing shear section parameter widgets."""
    return (
        {
            "widget_id": str(aggregate_size_widget_key),
            "group_id": "shear_section_parameters_basic",
            "kind": "number_input",
            "label": "Maximum aggregate size d_g (mm)",
            "widget_key": str(aggregate_size_widget_key),
            "shared_key": "d_g",
            "callback_key": str(aggregate_size_widget_key),
            "help_text": "Maximum aggregate size used in shear provisions (mm).",
            "default": float(aggregate_size_value),
        },
        {
            "widget_id": str(k_v_method_widget_key),
            "group_id": "shear_section_parameters_basic",
            "kind": "selectbox",
            "label": "k_v method",
            "widget_key": str(k_v_method_widget_key),
            "shared_key": "k_v_method",
            "callback_key": str(k_v_method_widget_key),
            "help_text": "Select the k_v method for shear capacity (AS 3600 8.2.4.2 vs 8.2.4.3).",
            "default": k_v_method_value,
            "options": list(k_v_method_options or ()),
        },
    )


def build_top_level_design_mode_widget_payloads(
    *,
    detailed_mode_value: Any,
    use_calculated_actions_value: Any,
    loads_edit_toggle_widget_key: Any,
    edit_sls_value: Any,
) -> tuple[dict[str, Any], ...]:
    """Return metadata payloads for the existing top-level Inputs mode controls."""
    return (
        {
            "widget_id": "inputs_detailed_mode_toggle",
            "group_id": "top_level_design_mode",
            "kind": "radio",
            "label": "Design mode",
            "widget_key": "inputs_detailed_mode_toggle",
            "shared_key": "inputs_detailed_mode",
            "callback_key": "inputs_detailed_mode_toggle",
            "help_text": (
                "Choose between the streamlined fast workflow and the full detailed "
                "design workspace."
            ),
            "default": bool(detailed_mode_value),
            "options": [False, True],
        },
        {
            "widget_id": "inputs_use_calculated_actions",
            "group_id": "design_actions_mode",
            "kind": "toggle",
            "label": "Use calculated design actions",
            "widget_key": "inputs_use_calculated_actions",
            "shared_key": "actions_source",
            "callback_key": "_on_inputs_use_calculated_actions_change",
            "help_text": (
                "When enabled, the design actions below are taken from the Design / "
                "SFD-BMD page and become read-only."
            ),
            "default": bool(use_calculated_actions_value),
            "options": [False, True],
        },
        {
            "widget_id": str(loads_edit_toggle_widget_key),
            "group_id": "design_actions_mode",
            "kind": "toggle",
            "label": "View SLS loads",
            "widget_key": str(loads_edit_toggle_widget_key),
            "shared_key": "loads_edit_toggle",
            "callback_key": str(loads_edit_toggle_widget_key),
            "help_text": (
                "Toggle which load set is shown below. ULS drives bending/shear; "
                "SLS drives crack/deflection."
            ),
            "default": bool(edit_sls_value),
            "options": [False, True],
        },
    )


def build_longitudinal_reinforcement_widget_payloads(
    *,
    section: str,
    cover_widget_key: Any,
    cover_shared_key: Any,
    cover_label: Any,
    cover_default: Any,
    cover_help_text: Any,
    row_values: Any,
    layout_mode_options: Any,
    count_options: Any,
    spacing_options: Any,
    bar_diameter_options: Any,
    diameter_label: Any,
) -> tuple[dict[str, Any], ...]:
    """Return metadata payloads for the existing bottom/top longitudinal widgets."""
    section_norm = "top" if str(section or "").strip().lower() == "top" else "bot"
    group_id = (
        "top_longitudinal_reinforcement"
        if section_norm == "top"
        else "bottom_longitudinal_reinforcement"
    )
    row_face = "top web" if section_norm == "top" else "bottom web"
    payloads: list[dict[str, Any]] = [
        {
            "widget_id": str(cover_widget_key),
            "group_id": group_id,
            "kind": "number_input",
            "label": str(cover_label),
            "widget_key": str(cover_widget_key),
            "shared_key": str(cover_shared_key),
            "callback_key": str(cover_widget_key),
            "help_text": str(cover_help_text),
            "default": float(cover_default),
        }
    ]
    valid_count_options = [
        int(option)
        for option in list(count_options or [])
        if int(option) != 1
    ]
    for row in list(row_values or ()):
        if not isinstance(row, dict):
            continue
        row_index = int(row.get("row_index") or 0)
        if row_index <= 0:
            continue
        mode_key = f"inputs_{section_norm}_row_{row_index}_mode"
        bars_key = f"inputs_{section_norm}_row_{row_index}_bars"
        spacing_key = f"inputs_{section_norm}_row_{row_index}_spacing"
        dia_key = f"inputs_{section_norm}_row_{row_index}_dia"
        mode_shared_key = f"{section_norm}_row_{row_index}_mode"
        bars_shared_key = f"{section_norm}_row_{row_index}_bars"
        spacing_shared_key = f"{section_norm}_row_{row_index}_spacing"
        dia_shared_key = f"{section_norm}_row_{row_index}_dia"
        mode_value = str(row.get("mode") or "Count")
        payloads.append(
            {
                "widget_id": mode_key,
                "group_id": group_id,
                "kind": "selectbox",
                "label": "Layout",
                "widget_key": mode_key,
                "shared_key": mode_shared_key,
                "callback_key": mode_key,
                "help_text": f"Choose whether Row {row_index} uses bar count or spacing.",
                "default": mode_value,
                "options": list(layout_mode_options or ()),
            }
        )
        if mode_value == "Count":
            payloads.append(
                {
                    "widget_id": bars_key,
                    "group_id": group_id,
                    "kind": "selectbox",
                    "label": "Bars",
                    "widget_key": bars_key,
                    "shared_key": bars_shared_key,
                    "callback_key": bars_key,
                    "help_text": f"Number of bars in {row_face} row {row_index}.",
                    "default": int(row.get("bars") or 0),
                    "options": valid_count_options,
                }
            )
        else:
            payloads.append(
                {
                    "widget_id": spacing_key,
                    "group_id": group_id,
                    "kind": "selectbox",
                    "label": "Spacing",
                    "widget_key": spacing_key,
                    "shared_key": spacing_shared_key,
                    "callback_key": spacing_key,
                    "help_text": f"Centre-to-centre spacing for {row_face} row {row_index} (mm).",
                    "default": int(row.get("spacing") or 200),
                    "options": list(spacing_options or ()),
                }
            )
        payloads.append(
            {
                "widget_id": dia_key,
                "group_id": group_id,
                "kind": "selectbox",
                "label": str(diameter_label),
                "widget_key": dia_key,
                "shared_key": dia_shared_key,
                "callback_key": dia_key,
                "help_text": f"Nominal bar diameter for {row_face} row {row_index} (mm).",
                "default": int(row.get("diameter") or 0),
                "options": list(bar_diameter_options or ()),
            }
        )
    return tuple(payloads)


def build_flange_reinforcement_basic_widget_payloads(
    *,
    reo_bar_diameters: Any,
    top_enabled_value: Any,
    top_mirror_value: Any,
    top_left_count_value: Any,
    top_left_diameter_value: Any,
    top_left_rows_value: Any,
    top_left_row_spacing_value: Any,
    top_left_clear_spacing_mode_value: Any,
    top_right_count_value: Any,
    top_right_diameter_value: Any,
    top_right_rows_value: Any,
    top_right_row_spacing_value: Any,
    top_right_clear_spacing_mode_value: Any,
    bottom_enabled_value: Any,
    bottom_mirror_value: Any,
    bottom_left_count_value: Any,
    bottom_left_diameter_value: Any,
    bottom_left_rows_value: Any,
    bottom_left_row_spacing_value: Any,
    bottom_left_clear_spacing_mode_value: Any,
    bottom_right_count_value: Any,
    bottom_right_diameter_value: Any,
    bottom_right_rows_value: Any,
    bottom_right_row_spacing_value: Any,
    bottom_right_clear_spacing_mode_value: Any,
) -> tuple[dict[str, Any], ...]:
    """Return metadata payloads for the existing flange reinforcement widgets."""
    group_id = "flange_reinforcement_basic"
    diameters = list(reo_bar_diameters or ())
    spacing_modes = ["count", "spacing"]

    def payload(
        *,
        shared_key: str,
        kind: str,
        label: str,
        default: Any,
        options: Any = None,
        help_text: str = "",
    ) -> dict[str, Any]:
        item = {
            "widget_id": f"inputs_{shared_key}",
            "group_id": group_id,
            "kind": kind,
            "label": label,
            "widget_key": f"inputs_{shared_key}",
            "shared_key": shared_key,
            "callback_key": f"inputs_{shared_key}",
            "default": default,
        }
        if help_text:
            item["help_text"] = help_text
        if options is not None:
            item["options"] = options
        return item

    widgets: list[dict[str, Any]] = [
        payload(
            shared_key="top_flange_reo_enabled",
            kind="selectbox",
            label="Enable top flange bars",
            help_text="Enable explicit top flange reinforcement groups.",
            default=bool(top_enabled_value),
            options=[False, True],
        ),
        payload(
            shared_key="top_flange_mirror_lr",
            kind="selectbox",
            label="Mirror top left/right",
            help_text="When enabled, the right-side top flange group mirrors the left-side values.",
            default=bool(top_mirror_value),
            options=[True, False],
        ),
        payload(
            shared_key="top_flange_left_count",
            kind="number_input",
            label="Top flange left bars",
            help_text="Total bars in top-left flange group.",
            default=float(top_left_count_value),
        ),
        payload(
            shared_key="top_flange_left_dia",
            kind="selectbox",
            label="Top flange left dia (mm)",
            default=int(top_left_diameter_value),
            options=diameters,
        ),
        payload(
            shared_key="top_flange_left_rows",
            kind="number_input",
            label="Top flange left rows",
            default=float(top_left_rows_value),
        ),
        payload(
            shared_key="top_flange_left_row_spacing",
            kind="number_input",
            label="Top flange left row spacing (mm)",
            default=float(top_left_row_spacing_value),
        ),
        payload(
            shared_key="top_flange_left_clear_spacing_mode",
            kind="selectbox",
            label="Top flange left clear spacing mode",
            default=str(top_left_clear_spacing_mode_value),
            options=spacing_modes,
        ),
        payload(
            shared_key="bot_flange_reo_enabled",
            kind="selectbox",
            label="Enable bottom flange bars",
            help_text="Enable explicit bottom flange reinforcement groups (I-sections only; ignored for T bottom flange).",
            default=bool(bottom_enabled_value),
            options=[False, True],
        ),
        payload(
            shared_key="bot_flange_mirror_lr",
            kind="selectbox",
            label="Mirror bottom left/right",
            help_text="When enabled, the right-side bottom flange group mirrors the left-side values.",
            default=bool(bottom_mirror_value),
            options=[True, False],
        ),
        payload(
            shared_key="bot_flange_left_count",
            kind="number_input",
            label="Bottom flange left bars",
            default=float(bottom_left_count_value),
        ),
        payload(
            shared_key="bot_flange_left_dia",
            kind="selectbox",
            label="Bottom flange left dia (mm)",
            default=int(bottom_left_diameter_value),
            options=diameters,
        ),
        payload(
            shared_key="bot_flange_left_rows",
            kind="number_input",
            label="Bottom flange left rows",
            default=float(bottom_left_rows_value),
        ),
        payload(
            shared_key="bot_flange_left_row_spacing",
            kind="number_input",
            label="Bottom flange left row spacing (mm)",
            default=float(bottom_left_row_spacing_value),
        ),
        payload(
            shared_key="bot_flange_left_clear_spacing_mode",
            kind="selectbox",
            label="Bottom flange left clear spacing mode",
            default=str(bottom_left_clear_spacing_mode_value),
            options=spacing_modes,
        ),
    ]
    if not bool(top_mirror_value):
        widgets.extend(
            [
                payload(
                    shared_key="top_flange_right_count",
                    kind="number_input",
                    label="Top flange right bars",
                    default=float(top_right_count_value),
                ),
                payload(
                    shared_key="top_flange_right_dia",
                    kind="selectbox",
                    label="Top flange right dia (mm)",
                    default=int(top_right_diameter_value),
                    options=diameters,
                ),
                payload(
                    shared_key="top_flange_right_rows",
                    kind="number_input",
                    label="Top flange right rows",
                    default=float(top_right_rows_value),
                ),
                payload(
                    shared_key="top_flange_right_row_spacing",
                    kind="number_input",
                    label="Top flange right row spacing (mm)",
                    default=float(top_right_row_spacing_value),
                ),
                payload(
                    shared_key="top_flange_right_clear_spacing_mode",
                    kind="selectbox",
                    label="Top flange right clear spacing mode",
                    default=str(top_right_clear_spacing_mode_value),
                    options=spacing_modes,
                ),
            ]
        )
    if not bool(bottom_mirror_value):
        widgets.extend(
            [
                payload(
                    shared_key="bot_flange_right_count",
                    kind="number_input",
                    label="Bottom flange right bars",
                    default=float(bottom_right_count_value),
                ),
                payload(
                    shared_key="bot_flange_right_dia",
                    kind="selectbox",
                    label="Bottom flange right dia (mm)",
                    default=int(bottom_right_diameter_value),
                    options=diameters,
                ),
                payload(
                    shared_key="bot_flange_right_rows",
                    kind="number_input",
                    label="Bottom flange right rows",
                    default=float(bottom_right_rows_value),
                ),
                payload(
                    shared_key="bot_flange_right_row_spacing",
                    kind="number_input",
                    label="Bottom flange right row spacing (mm)",
                    default=float(bottom_right_row_spacing_value),
                ),
                payload(
                    shared_key="bot_flange_right_clear_spacing_mode",
                    kind="selectbox",
                    label="Bottom flange right clear spacing mode",
                    default=str(bottom_right_clear_spacing_mode_value),
                    options=spacing_modes,
                ),
            ]
        )
    return tuple(widgets)


def build_flange_transverse_basic_widget_payloads(
    *,
    reo_bar_diameters: Any,
    top_enabled_value: Any,
    top_diameter_value: Any,
    top_spacing_value: Any,
    top_legs_value: Any,
    bottom_enabled_value: Any,
    bottom_diameter_value: Any,
    bottom_spacing_value: Any,
    bottom_legs_value: Any,
) -> tuple[dict[str, Any], ...]:
    """Return metadata payloads for the existing flange transverse widgets."""
    diameters = list(reo_bar_diameters or ())
    return (
        {
            "widget_id": "inputs_top_flange_transverse_enabled",
            "group_id": "flange_transverse_basic",
            "kind": "selectbox",
            "label": "Enable top flange transverse",
            "widget_key": "inputs_top_flange_transverse_enabled",
            "shared_key": "top_flange_transverse_enabled",
            "callback_key": "inputs_top_flange_transverse_enabled",
            "default": bool(top_enabled_value),
            "options": [False, True],
        },
        {
            "widget_id": "inputs_top_flange_transverse_dia",
            "group_id": "flange_transverse_basic",
            "kind": "selectbox",
            "label": "Top flange transverse dia (mm)",
            "widget_key": "inputs_top_flange_transverse_dia",
            "shared_key": "top_flange_transverse_dia",
            "callback_key": "inputs_top_flange_transverse_dia",
            "default": int(top_diameter_value),
            "options": diameters,
        },
        {
            "widget_id": "inputs_top_flange_transverse_spacing",
            "group_id": "flange_transverse_basic",
            "kind": "number_input",
            "label": "Top flange transverse spacing (mm)",
            "widget_key": "inputs_top_flange_transverse_spacing",
            "shared_key": "top_flange_transverse_spacing",
            "callback_key": "inputs_top_flange_transverse_spacing",
            "default": float(top_spacing_value),
        },
        {
            "widget_id": "inputs_top_flange_transverse_legs",
            "group_id": "flange_transverse_basic",
            "kind": "number_input",
            "label": "Top flange transverse legs",
            "widget_key": "inputs_top_flange_transverse_legs",
            "shared_key": "top_flange_transverse_legs",
            "callback_key": "inputs_top_flange_transverse_legs",
            "default": float(top_legs_value),
        },
        {
            "widget_id": "inputs_bot_flange_transverse_enabled",
            "group_id": "flange_transverse_basic",
            "kind": "selectbox",
            "label": "Enable bottom flange transverse",
            "widget_key": "inputs_bot_flange_transverse_enabled",
            "shared_key": "bot_flange_transverse_enabled",
            "callback_key": "inputs_bot_flange_transverse_enabled",
            "default": bool(bottom_enabled_value),
            "options": [False, True],
        },
        {
            "widget_id": "inputs_bot_flange_transverse_dia",
            "group_id": "flange_transverse_basic",
            "kind": "selectbox",
            "label": "Bottom flange transverse dia (mm)",
            "widget_key": "inputs_bot_flange_transverse_dia",
            "shared_key": "bot_flange_transverse_dia",
            "callback_key": "inputs_bot_flange_transverse_dia",
            "default": int(bottom_diameter_value),
            "options": diameters,
        },
        {
            "widget_id": "inputs_bot_flange_transverse_spacing",
            "group_id": "flange_transverse_basic",
            "kind": "number_input",
            "label": "Bottom flange transverse spacing (mm)",
            "widget_key": "inputs_bot_flange_transverse_spacing",
            "shared_key": "bot_flange_transverse_spacing",
            "callback_key": "inputs_bot_flange_transverse_spacing",
            "default": float(bottom_spacing_value),
        },
        {
            "widget_id": "inputs_bot_flange_transverse_legs",
            "group_id": "flange_transverse_basic",
            "kind": "number_input",
            "label": "Bottom flange transverse legs",
            "widget_key": "inputs_bot_flange_transverse_legs",
            "shared_key": "bot_flange_transverse_legs",
            "callback_key": "inputs_bot_flange_transverse_legs",
            "default": float(bottom_legs_value),
        },
    )
