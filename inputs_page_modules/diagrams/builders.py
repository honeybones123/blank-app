"""Typed Inputs-page diagram request builders."""

from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
from typing import Any

from section_props.reo_layout import resolve_longitudinal_bars_from_layout
from section_props.shape_utils import normalise_shape_name
from inputs_v2.engineering.shear_detailing import (
    ShearDetailingInput,
    calculate_shear_detailing,
)

from .contracts import BEAM_3D_HASH_FIELDS, SECTION_2D_HASH_FIELDS
from .models import (
    Beam3DFigureRequestViewModel,
    InputsDiagramSectionViewModel,
    InputsDiagramSourceSnapshot,
    Section2DFigureRequestViewModel,
)


def stable_diagram_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def stable_diagram_hash(value: Any) -> str:
    return hashlib.sha256(stable_diagram_json(value).encode("utf-8")).hexdigest()


def _hash_dataclass_fields(model: Any, fields: tuple[str, ...]) -> str:
    payload = asdict(model)
    return stable_diagram_hash({field: payload.get(field) for field in fields})


_CAGE_ERROR_MESSAGES = {
    "shear_cage_topology_unavailable": "The selected shear-link cage cannot be constructed.",
    "shear_cage_longitudinal_bar_collision": "An internal shear-link leg clashes with longitudinal reinforcement.",
    "internal_leg_anchorage_failed": "The internal shear-link legs do not have enough depth for their anchorage envelope.",
    "longitudinal_bar_restraint_failed": "One or more longitudinal bars lie outside the closed shear-link cage.",
}


def _detailing_validation_errors(layout: dict[str, Any], shared_state: dict[str, Any]) -> tuple[str, ...]:
    """Project existing factual detailing checks into diagram evidence."""

    reo_layout = dict(layout.get("reo_layout") or {})
    errors = [str(value) for value in (reo_layout.get("warnings") or []) if str(value).strip()]
    # T/I layout construction keeps a failed placement reason on the section
    # layout because no invalid bar coordinates should be drawn.  Surface that
    # existing factual result through the same red diagram shell used by RECT;
    # this display boundary must not recalculate or reinterpret the failure.
    reo_error = str(layout.get("reo_error") or "").strip()
    if reo_error:
        errors.append(reo_error)
    reo = dict(layout.get("reo") or {})
    dims = dict(layout.get("dims") or {})
    link_diameter = float(shared_state.get("lig_d", reo.get("lig_d", 0.0)) or 0.0)
    link_legs = int(shared_state.get("lig_legs", reo.get("lig_legs", 0)) or 0)
    if link_diameter <= 0.0 or link_legs < 2:
        return tuple(dict.fromkeys(errors))

    shape_key = normalise_shape_name(str(layout.get("shape_name", "RECT") or "RECT"))
    if shape_key == "T":
        width = float(dims.get("bw", 0.0) or 0.0)
        web_origin = (float(dims.get("bf", width) or width) - width) / 2.0
    elif shape_key == "I":
        width = float(dims.get("tw", 0.0) or 0.0)
        web_origin = (float(dims.get("bf", width) or width) - width) / 2.0
    else:
        width = float(dims.get("b", 0.0) or 0.0)
        web_origin = 0.0
    depth = float(dims.get("D", 0.0) or 0.0)
    cover_side = float(reo.get("cover_side", 40.0) or 40.0)
    bars_list: list[tuple[float, float, float]] = []
    for face in ("bottom", "top"):
        for layer in (reo_layout.get(face) or []):
            x_values = tuple(layer.get("x") or ())
            y_raw = layer.get("y", 0.0)
            db_raw = layer.get("db", 0.0)
            y_values = tuple(y_raw) if isinstance(y_raw, (list, tuple)) else ()
            db_values = tuple(db_raw) if isinstance(db_raw, (list, tuple)) else ()
            for index, x in enumerate(x_values):
                y = y_values[index] if index < len(y_values) else y_raw
                diameter = db_values[index] if index < len(db_values) else db_raw
                # Older saved layouts may carry a one-item row array. Expand
                # it at this display boundary; never mutate or rehydrate the
                # authoritative reinforcement state.
                if isinstance(y, (list, tuple)):
                    y = y[0] if y else 0.0
                if isinstance(diameter, (list, tuple)):
                    diameter = diameter[0] if diameter else 0.0
                diameter_value = float(diameter or 0.0)
                if diameter_value > 0.0:
                    bars_list.append(
                        (float(x) - web_origin, float(y or 0.0), diameter_value)
                    )
    bars = tuple(bars_list)
    result = calculate_shear_detailing(
        ShearDetailingInput(
            reinforcement_area_mm2=0.0,
            spacing_mm=float(shared_state.get("s_lig", reo.get("s_lig", 0.0)) or 0.0) or None,
            concrete_strength_mpa=float(shared_state.get("fc", reo.get("fc", 0.0)) or 0.0),
            web_width_mm=width,
            reinforcement_strength_mpa=float(shared_state.get("fsyv", reo.get("fsyv", 500.0)) or 500.0),
            section_depth_mm=depth,
            effective_legs=link_legs,
            link_diameter_mm=link_diameter,
            side_cover_mm=cover_side,
            nominal_aggregate_size_mm=float(shared_state.get("dagg", reo.get("dagg", 20.0)) or 20.0),
            longitudinal_bar_coordinates_mm=bars,
        )
    )
    if not result.transverse_fit_ok:
        errors.append("The selected shear-link legs do not fit within the available section width and cover.")
    if not result.transverse_clear_spacing_ok:
        errors.append(
            "Clear spacing between shear-link legs is below the required "
            f"{result.transverse_minimum_clear_spacing_mm:g} mm."
        )
    if result.transverse_fit_ok and result.transverse_max_leg_spacing_mm > result.transverse_spacing_limit_mm + 1e-9:
        errors.append(
            "Transverse spacing between shear-link legs exceeds the "
            f"{result.transverse_spacing_limit_mm:g} mm limit."
        )
    errors.extend(_CAGE_ERROR_MESSAGES.get(code, code.replace("_", " ").capitalize()) for code in result.cage_rejection_codes)
    return tuple(dict.fromkeys(errors))


def build_section_2d_request_view_model(
    source: InputsDiagramSourceSnapshot,
) -> Section2DFigureRequestViewModel:
    layout = dict(source.layout or {})
    dims = dict(layout.get("dims") or {})
    reo = dict(layout.get("reo") or {})
    validation_errors = _detailing_validation_errors(layout, dict(source.shared_state or {}))
    model = Section2DFigureRequestViewModel(
        shape_name=str(layout.get("shape_name", "Rectangle (b x D)") or "Rectangle (b x D)"),
        dims=dims,
        reo=reo,
        show_shear=True,
        show_dn=False,
        dn=0.0,
        tension_face=source.tension_face,
        fallback_cover_side=float(source.fallback_cover_side),
        fallback_cover_top=float(source.fallback_cover_top),
        fallback_cover_bot=float(source.fallback_cover_bot),
        validation_errors=validation_errors,
    )
    return replace(model, display_hash=_hash_dataclass_fields(model, SECTION_2D_HASH_FIELDS))


def build_beam_3d_request_view_model(
    source: InputsDiagramSourceSnapshot,
) -> Beam3DFigureRequestViewModel:
    layout = dict(source.layout or {})
    dims = dict(layout.get("dims") or {})
    reo = dict(layout.get("reo") or {})
    shared_state = dict(source.shared_state or {})
    shape_name = str(layout.get("shape_name", "Rectangle (b x D)") or "Rectangle (b x D)")
    shape_key = normalise_shape_name(shape_name)
    fallback_width = float(dims.get("b", source.fallback_width) or source.fallback_width)
    depth = float(dims.get("D", source.outline_depth or source.fallback_depth) or source.fallback_depth)
    span = float(source.span_length or 3000.0)
    l_plot = max(min(span, 3000.0), 400.0)
    cover_bot = float(reo.get("cover_bot", source.fallback_cover_bot) or source.fallback_cover_bot)
    cover_top = float(reo.get("cover_top", source.fallback_cover_top) or source.fallback_cover_top)
    cover_side_raw = reo.get("cover_side")
    if cover_side_raw is None:
        cover_side_raw = min(cover_top, cover_bot)
    cover_side = float(cover_side_raw)
    lig_d = float(shared_state.get("lig_d", reo.get("lig_d", 0.0)) or 0.0)
    lig_legs = int(shared_state.get("lig_legs", reo.get("lig_legs", 0)) or 0)
    s_lig = float(shared_state.get("s_lig", reo.get("s_lig", 200.0)) or 200.0)
    reo_layout = dict(layout.get("reo_layout") or {"bottom": [], "top": []})
    validation_errors = _detailing_validation_errors(layout, shared_state)
    resolved_bars = None
    if shape_key in ("T", "I"):
        has_layout_bars = any(
            bool(band.get("x"))
            for bands in reo_layout.values()
            if isinstance(bands, list)
            for band in bands
            if isinstance(band, dict)
        )
        resolved_bars = (
            tuple(
                dict(bar)
                for bar in resolve_longitudinal_bars_from_layout(
                    shape_name=shape_name,
                    dims=dims,
                    reo_layout=reo_layout,
                )
            )
            if has_layout_bars
            else ()
        )
    model = Beam3DFigureRequestViewModel(
        shape_name=shape_name,
        shape_key=shape_key,
        outline_points=tuple(tuple(point) for point in source.outline_points),
        b_box=float(source.outline_width or fallback_width),
        D=float(source.outline_depth or depth),
        L_plot=float(l_plot),
        fallback_width=float(fallback_width),
        cover_bot=float(cover_bot),
        cover_top=float(cover_top),
        cover_side=float(cover_side),
        lig_d=float(lig_d),
        lig_legs=int(lig_legs),
        s_lig=float(s_lig),
        reo_layout=reo_layout,
        cage=dict(layout.get("cage") or {}),
        resolved_bars=resolved_bars,
        validation_errors=validation_errors,
    )
    return replace(model, display_hash=_hash_dataclass_fields(model, BEAM_3D_HASH_FIELDS))


def build_inputs_diagram_view_model(
    source: InputsDiagramSourceSnapshot,
) -> InputsDiagramSectionViewModel:
    section_2d = build_section_2d_request_view_model(source)
    beam_3d = build_beam_3d_request_view_model(source)
    display_hash = stable_diagram_hash(
        {
            "section_2d": section_2d.display_hash,
            "beam_3d": beam_3d.display_hash,
        }
    )
    return InputsDiagramSectionViewModel(
        section_2d=section_2d,
        beam_3d=beam_3d,
        display_hash=display_hash,
    )
