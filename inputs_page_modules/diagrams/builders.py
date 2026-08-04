"""Typed Inputs-page diagram request builders."""

from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
from typing import Any

from section_props.reo_layout import resolve_longitudinal_bars_from_layout
from section_props.shape_utils import normalise_shape_name

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


def build_section_2d_request_view_model(
    source: InputsDiagramSourceSnapshot,
) -> Section2DFigureRequestViewModel:
    layout = dict(source.layout or {})
    dims = dict(layout.get("dims") or {})
    reo = dict(layout.get("reo") or {})
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
    resolved_bars = None
    if shape_key in ("T", "I"):
        resolved_bars = tuple(
            dict(bar)
            for bar in resolve_longitudinal_bars_from_layout(
                shape_name=shape_name,
                dims=dims,
                reo_layout=reo_layout,
            )
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

