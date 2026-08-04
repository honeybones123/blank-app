from __future__ import annotations

import copy
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _run_side(module: Any, *, legacy: bool, inputs_detailed_mode: bool, sec_shape: str) -> dict[str, Any]:
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route_bridge

    events: list[dict[str, Any]] = []
    ss: dict[str, Any] = {"active_beam_id": "B1"}

    def fast_get_param(key: str, default: Any = None) -> Any:
        return {"D": 600, "b": 300}.get(key, default)

    def mark(label: str) -> None:
        events.append({"fn": "mark", "label": label})

    def sub_mark(label: str) -> None:
        events.append({"fn": "sub_mark", "label": label})

    def top_layout(**kwargs: Any) -> tuple:
        events.append(
            {
                "fn": "top_layout",
                "inputs_detailed_mode": kwargs.get("inputs_detailed_mode"),
                "fast_focus_section": kwargs.get("fast_focus_section"),
            }
        )
        return (
            "bottom-slot",
            "shear-slot",
            "model-slot",
            "actions-slot",
            "geometry-slot",
            "right-diagram",
        )

    def design_actions(**kwargs: Any) -> None:
        events.append(
            {
                "fn": "design_actions",
                "actions_slot": kwargs.get("actions_slot"),
                "inputs_detailed_mode": kwargs.get("inputs_detailed_mode"),
            }
        )

    def geometry(**kwargs: Any) -> None:
        events.append(
            {
                "fn": "geometry",
                "geometry_slot": kwargs.get("geometry_slot"),
                "right_diagram": kwargs.get("right_diagram"),
                "model_slot": kwargs.get("model_slot"),
                "inputs_detailed_mode": kwargs.get("inputs_detailed_mode"),
            }
        )

    def columns(count: int, **kwargs: Any) -> tuple[str, str, str]:
        events.append({"fn": "columns", "count": count, "kwargs": dict(kwargs)})
        return "col-bot", "col-top", "col-shear"

    def normalize_shape(value: str) -> str:
        events.append({"fn": "normalize_shape", "value": value})
        return "T" if value in {"T", "I"} else "RECT"

    def pair_labels(value: str, *, variant: str) -> tuple[str, str]:
        events.append({"fn": "pair_labels", "value": value, "variant": variant})
        return f"bottom-{variant}", f"top-{variant}"

    def bottom(**kwargs: Any) -> None:
        events.append(
            {
                "fn": "bottom",
                "col": kwargs.get("col_bot_reo"),
                "mode": kwargs.get("inputs_detailed_mode"),
                "shape": kwargs.get("sec_shape_reo_ui"),
                "is_ti": kwargs.get("is_ti_reo_ui"),
                "header": kwargs.get("bot_hdr"),
            }
        )

    def top(**kwargs: Any) -> None:
        events.append(
            {
                "fn": "top",
                "col": kwargs.get("col_top_reo"),
                "mode": kwargs.get("inputs_detailed_mode"),
                "shape": kwargs.get("sec_shape_reo_ui"),
                "is_ti": kwargs.get("is_ti_reo_ui"),
                "header": kwargs.get("top_hdr"),
            }
        )

    def shear(**kwargs: Any) -> None:
        events.append(
            {
                "fn": "shear",
                "col": kwargs.get("col_shear_mat"),
                "mode": kwargs.get("inputs_detailed_mode"),
                "focus": kwargs.get("fast_focus_section"),
                "corrected": kwargs.get("corrected_invalid_shear_state"),
            }
        )

    def flange(**kwargs: Any) -> None:
        events.append({"fn": "flange", "keys": sorted(kwargs.keys())})

    def support(**kwargs: Any) -> None:
        events.append({"fn": "support", "mode": kwargs.get("inputs_detailed_mode")})

    def autopersist(*, ss: dict) -> bool:
        events.append({"fn": "autopersist", "ss_keys": sorted(ss.keys())})
        return True

    kwargs = {
        "ss": ss,
        "inputs_detailed_mode": inputs_detailed_mode,
        "sync_callbacks": {"sync_a": object()},
        "inputs_render_audit": {"design_guide_rendered": "yes"},
        "fast_focus_section": "geometry",
        "fast_get_param": fast_get_param,
        "corrected_invalid_shear_state": True,
        "mark": mark,
        "sub_mark": sub_mark,
    }

    if legacy:
        originals = {
            "st": legacy_inputs_page.st,
            "top_layout": legacy_inputs_page.render_inputs_top_section_layout_slots_coordinator,
            "design_actions": legacy_inputs_page.render_inputs_design_actions_section_current_coordinator,
            "geometry": legacy_inputs_page.render_inputs_geometry_materials_top_section_current_coordinator,
            "normalize": legacy_inputs_page.normalized_sec_shape_ui,
            "labels": legacy_inputs_page.main_longitudinal_reo_pair_labels,
            "bottom": legacy_inputs_page.render_inputs_bottom_reinforcement_column_current_coordinator,
            "top": legacy_inputs_page.render_inputs_top_reinforcement_column_current_coordinator,
            "shear": legacy_inputs_page.render_inputs_shear_reinforcement_column_current_coordinator,
            "flange": legacy_inputs_page.render_inputs_flange_reinforcement_current_coordinator,
            "support": legacy_inputs_page.render_inputs_detailed_support_lower_row_current_coordinator,
            "autopersist": legacy_inputs_page.render_inputs_post_widget_autopersist_current_coordinator,
        }
        try:
            legacy_inputs_page.st = SimpleNamespace(
                columns=columns,
                session_state={"inputs_sec_shape": sec_shape, "sec_shape": "RECT"},
            )
            legacy_inputs_page.render_inputs_top_section_layout_slots_coordinator = top_layout
            legacy_inputs_page.render_inputs_design_actions_section_current_coordinator = design_actions
            legacy_inputs_page.render_inputs_geometry_materials_top_section_current_coordinator = geometry
            legacy_inputs_page.normalized_sec_shape_ui = normalize_shape
            legacy_inputs_page.main_longitudinal_reo_pair_labels = pair_labels
            legacy_inputs_page.render_inputs_bottom_reinforcement_column_current_coordinator = bottom
            legacy_inputs_page.render_inputs_top_reinforcement_column_current_coordinator = top
            legacy_inputs_page.render_inputs_shear_reinforcement_column_current_coordinator = shear
            legacy_inputs_page.render_inputs_flange_reinforcement_current_coordinator = flange
            legacy_inputs_page.render_inputs_detailed_support_lower_row_current_coordinator = support
            legacy_inputs_page.render_inputs_post_widget_autopersist_current_coordinator = autopersist
            result = module.render_inputs_widget_sections_current_coordinator(**kwargs)
        finally:
            legacy_inputs_page.st = originals["st"]
            legacy_inputs_page.render_inputs_top_section_layout_slots_coordinator = originals["top_layout"]
            legacy_inputs_page.render_inputs_design_actions_section_current_coordinator = originals[
                "design_actions"
            ]
            legacy_inputs_page.render_inputs_geometry_materials_top_section_current_coordinator = originals[
                "geometry"
            ]
            legacy_inputs_page.normalized_sec_shape_ui = originals["normalize"]
            legacy_inputs_page.main_longitudinal_reo_pair_labels = originals["labels"]
            legacy_inputs_page.render_inputs_bottom_reinforcement_column_current_coordinator = originals["bottom"]
            legacy_inputs_page.render_inputs_top_reinforcement_column_current_coordinator = originals["top"]
            legacy_inputs_page.render_inputs_shear_reinforcement_column_current_coordinator = originals["shear"]
            legacy_inputs_page.render_inputs_flange_reinforcement_current_coordinator = originals["flange"]
            legacy_inputs_page.render_inputs_detailed_support_lower_row_current_coordinator = originals[
                "support"
            ]
            legacy_inputs_page.render_inputs_post_widget_autopersist_current_coordinator = originals[
                "autopersist"
            ]
    else:
        originals = {
            "top_layout": route_bridge.render_inputs_top_section_layout_slots_coordinator,
            "design_actions": route_bridge.render_inputs_design_actions_section_current_coordinator,
            "geometry": route_bridge.render_inputs_geometry_materials_top_section_current_coordinator,
            "columns": route_bridge.create_reinforcement_columns,
            "shape": route_bridge.get_inputs_section_shape_for_reinforcement,
            "normalize": route_bridge.normalized_sec_shape_ui,
            "labels": route_bridge.main_longitudinal_reo_pair_labels,
            "bottom": route_bridge.render_inputs_bottom_reinforcement_column_current_coordinator,
            "top": route_bridge.render_inputs_top_reinforcement_column_current_coordinator,
            "shear": route_bridge.render_inputs_shear_reinforcement_column_current_coordinator,
            "flange": route_bridge.render_inputs_flange_reinforcement_current_coordinator,
            "support": route_bridge.render_inputs_detailed_support_lower_row_current_coordinator,
            "autopersist": route_bridge.render_inputs_post_widget_autopersist_current_coordinator,
        }
        try:
            route_bridge.render_inputs_top_section_layout_slots_coordinator = top_layout
            route_bridge.render_inputs_design_actions_section_current_coordinator = design_actions
            route_bridge.render_inputs_geometry_materials_top_section_current_coordinator = geometry
            route_bridge.create_reinforcement_columns = lambda: columns(3, gap="large")
            route_bridge.get_inputs_section_shape_for_reinforcement = lambda: sec_shape
            route_bridge.normalized_sec_shape_ui = normalize_shape
            route_bridge.main_longitudinal_reo_pair_labels = pair_labels
            route_bridge.render_inputs_bottom_reinforcement_column_current_coordinator = bottom
            route_bridge.render_inputs_top_reinforcement_column_current_coordinator = top
            route_bridge.render_inputs_shear_reinforcement_column_current_coordinator = shear
            route_bridge.render_inputs_flange_reinforcement_current_coordinator = flange
            route_bridge.render_inputs_detailed_support_lower_row_current_coordinator = support
            route_bridge.render_inputs_post_widget_autopersist_current_coordinator = autopersist
            result = module.render_inputs_widget_sections_current_coordinator(**kwargs)
        finally:
            route_bridge.render_inputs_top_section_layout_slots_coordinator = originals["top_layout"]
            route_bridge.render_inputs_design_actions_section_current_coordinator = originals["design_actions"]
            route_bridge.render_inputs_geometry_materials_top_section_current_coordinator = originals[
                "geometry"
            ]
            route_bridge.create_reinforcement_columns = originals["columns"]
            route_bridge.get_inputs_section_shape_for_reinforcement = originals["shape"]
            route_bridge.normalized_sec_shape_ui = originals["normalize"]
            route_bridge.main_longitudinal_reo_pair_labels = originals["labels"]
            route_bridge.render_inputs_bottom_reinforcement_column_current_coordinator = originals["bottom"]
            route_bridge.render_inputs_top_reinforcement_column_current_coordinator = originals["top"]
            route_bridge.render_inputs_shear_reinforcement_column_current_coordinator = originals["shear"]
            route_bridge.render_inputs_flange_reinforcement_current_coordinator = originals["flange"]
            route_bridge.render_inputs_detailed_support_lower_row_current_coordinator = originals["support"]
            route_bridge.render_inputs_post_widget_autopersist_current_coordinator = originals["autopersist"]

    return {"events": events, "result": result}


class _ContextRecorder:
    def __init__(self, events: list[dict[str, Any]], label: str) -> None:
        self._events = events
        self._label = label

    def __enter__(self) -> "_ContextRecorder":
        self._events.append({"fn": "enter", "label": self._label})
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        self._events.append({"fn": "exit", "label": self._label})
        return False


def _run_top_column_side(module: Any, *, load_pressed: bool, is_ti: bool) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    session_state: dict[str, Any] = {
        "active_beam_id": "B1",
        "page_slug": "inputs",
        "rowgap_top": 65.0,
    }

    def columns(spec: Any, **kwargs: Any) -> tuple[_ContextRecorder, _ContextRecorder]:
        events.append({"fn": "columns", "spec": list(spec), "kwargs": dict(kwargs)})
        return (
            _ContextRecorder(events, "header-title"),
            _ContextRecorder(events, "header-info"),
        )

    def markdown(text: str, **kwargs: Any) -> None:
        events.append({"fn": "markdown", "text": str(text), "kwargs": dict(kwargs)})

    def subheader(text: str, **kwargs: Any) -> None:
        events.append({"fn": "subheader", "text": str(text), "kwargs": dict(kwargs)})

    def divider() -> None:
        events.append({"fn": "divider"})

    def button(label: str, **kwargs: Any) -> bool:
        events.append({"fn": "button", "label": label, "kwargs": dict(kwargs)})
        return load_pressed

    def caption(text: str, **kwargs: Any) -> None:
        events.append({"fn": "caption", "text": str(text), "kwargs": dict(kwargs)})

    def info_i_button(**kwargs: Any) -> _ContextRecorder:
        events.append({"fn": "info_i_button", "kwargs": dict(kwargs)})
        return _ContextRecorder(events, "info")

    def audit(label: str) -> dict[str, Any]:
        events.append({"fn": "audit", "label": label})
        return {"label": label}

    def widget_key(shared_key: str, *, prefix: str = "") -> str:
        events.append({"fn": "widget_key", "shared_key": shared_key, "prefix": prefix})
        return f"{prefix}{shared_key}"

    def seed(widget_key_value: str, shared_key: str, default: Any) -> None:
        events.append(
            {
                "fn": "seed",
                "widget_key": widget_key_value,
                "shared_key": shared_key,
                "default": default,
            }
        )
        session_state.setdefault(widget_key_value, session_state.get(shared_key, default))

    def row_config(**kwargs: Any) -> None:
        events.append(
            {
                "fn": "row_config",
                "page_prefix": kwargs.get("page_prefix"),
                "section": kwargs.get("section"),
                "rowgap_widget_key": kwargs.get("rowgap_widget_key"),
                "rowgap_default": kwargs.get("rowgap_default"),
                "rowgap_help_text": kwargs.get("rowgap_help_text"),
                "sec_shape": kwargs.get("sec_shape"),
            }
        )

    def reo_rows(**kwargs: Any) -> None:
        events.append(
            {
                "fn": "reo_rows",
                "page_prefix": kwargs.get("page_prefix"),
                "section": kwargs.get("section"),
                "layout_modes": list(kwargs.get("layout_modes") or []),
                "count_options": list(kwargs.get("count_options") or []),
                "spacing_options": list(kwargs.get("spacing_options") or []),
                "dia_options": list(kwargs.get("dia_options") or []),
                "single_column": kwargs.get("single_column"),
                "sec_shape": kwargs.get("sec_shape"),
            }
        )

    def fast_get_param(key: str, default: Any = None) -> Any:
        events.append({"fn": "fast_get_param", "key": key, "default": default})
        return {"cover_top": 45.0}.get(key, default)

    def number_row(*args: Any, **kwargs: Any) -> None:
        sync_arg = args[3] if len(args) > 3 and isinstance(args[3], dict) else {}
        events.append(
            {
                "fn": "number_row",
                "args": list(args[:3]),
                "sync_keys": sorted(sync_arg.keys()),
                "kwargs": dict(kwargs),
            }
        )

    originals = {
        "st": module.st,
        "info_i_button": module.info_i_button,
        "audit": module._longitudinal_reo_widget_audit_snapshot,
        "widget_key": module.get_widget_key_for_shared,
        "seed": module.seed_widget_from_shared,
        "row_config": module.render_longitudinal_reo_row_config_controls,
        "reo_rows": module.render_longitudinal_reo_rows,
        "number_row": module.number_row,
    }
    try:
        module.st = SimpleNamespace(
            session_state=session_state,
            columns=columns,
            markdown=markdown,
            subheader=subheader,
            divider=divider,
            button=button,
            caption=caption,
        )
        module.info_i_button = info_i_button
        module._longitudinal_reo_widget_audit_snapshot = audit
        module.get_widget_key_for_shared = widget_key
        module.seed_widget_from_shared = seed
        module.render_longitudinal_reo_row_config_controls = row_config
        module.render_longitudinal_reo_rows = reo_rows
        module.number_row = number_row
        result = module.render_inputs_top_reinforcement_column_current_coordinator(
            col_top_reo=_ContextRecorder(events, "top-column"),
            inputs_detailed_mode=True,
            sync_callbacks={"sync_a": object()},
            fast_get_param=fast_get_param,
            sec_shape_reo_ui="T",
            is_ti_reo_ui=is_ti,
            top_hdr="Top reinforcement",
        )
    finally:
        module.st = originals["st"]
        module.info_i_button = originals["info_i_button"]
        module._longitudinal_reo_widget_audit_snapshot = originals["audit"]
        module.get_widget_key_for_shared = originals["widget_key"]
        module.seed_widget_from_shared = originals["seed"]
        module.render_longitudinal_reo_row_config_controls = originals["row_config"]
        module.render_longitudinal_reo_rows = originals["reo_rows"]
        module.number_row = originals["number_row"]

    return {"events": events, "result": result}


def _run_bottom_column_side(
    module: Any,
    *,
    load_pressed: bool,
    is_ti: bool,
    inputs_detailed_mode: bool,
    dev_mode: bool,
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    session_state: dict[str, Any] = {
        "active_beam_id": "B1",
        "page_slug": "inputs",
        "rowgap_bot": 70.0,
        "_dev_mode": dev_mode,
        "bot1_count": 3,
        "db_bot_1": 20,
        "bot_row_1_bars": 3,
        "bot_row_1_dia": 20,
        "inputs_bot1_count": 3,
        "inputs_db_bot_1": 20,
        "inputs_bot_row_1_bars": 3,
        "inputs_bot_row_1_dia": 20,
    }

    def columns(spec: Any, **kwargs: Any) -> tuple[_ContextRecorder, _ContextRecorder]:
        events.append({"fn": "columns", "spec": list(spec), "kwargs": dict(kwargs)})
        return (
            _ContextRecorder(events, "header-title"),
            _ContextRecorder(events, "header-info"),
        )

    def markdown(text: str, **kwargs: Any) -> None:
        events.append({"fn": "markdown", "text": str(text), "kwargs": dict(kwargs)})

    def subheader(text: str, **kwargs: Any) -> None:
        events.append({"fn": "subheader", "text": str(text), "kwargs": dict(kwargs)})

    def divider() -> None:
        events.append({"fn": "divider"})

    def button(label: str, **kwargs: Any) -> bool:
        events.append({"fn": "button", "label": label, "kwargs": dict(kwargs)})
        return load_pressed

    def caption(text: str, **kwargs: Any) -> None:
        events.append({"fn": "caption", "text": str(text), "kwargs": dict(kwargs)})

    def info_i_button(**kwargs: Any) -> _ContextRecorder:
        events.append({"fn": "info_i_button", "kwargs": dict(kwargs)})
        return _ContextRecorder(events, "info")

    def audit(label: str) -> dict[str, Any]:
        events.append({"fn": "audit", "label": label})
        return {"label": label}

    def widget_key(shared_key: str, *, prefix: str = "") -> str:
        events.append({"fn": "widget_key", "shared_key": shared_key, "prefix": prefix})
        return f"{prefix}{shared_key}"

    def seed(widget_key_value: str, shared_key: str, default: Any) -> None:
        events.append(
            {
                "fn": "seed",
                "widget_key": widget_key_value,
                "shared_key": shared_key,
                "default": default,
            }
        )
        session_state.setdefault(widget_key_value, session_state.get(shared_key, default))

    def row_config(**kwargs: Any) -> None:
        events.append(
            {
                "fn": "row_config",
                "page_prefix": kwargs.get("page_prefix"),
                "section": kwargs.get("section"),
                "rowgap_widget_key": kwargs.get("rowgap_widget_key"),
                "rowgap_default": kwargs.get("rowgap_default"),
                "rowgap_help_text": kwargs.get("rowgap_help_text"),
                "sec_shape": kwargs.get("sec_shape"),
            }
        )

    def recommendation_panel(**kwargs: Any) -> None:
        events.append({"fn": "bottom_recommendation_panel", "kwargs": dict(kwargs)})

    def agent_debug(message: str, data: dict[str, Any] | None = None, **kwargs: Any) -> None:
        events.append(
            {
                "fn": "agent_debug",
                "message": message,
                "data": data,
                "kwargs": dict(kwargs),
            }
        )

    def reo_rows(**kwargs: Any) -> None:
        events.append(
            {
                "fn": "reo_rows",
                "page_prefix": kwargs.get("page_prefix"),
                "section": kwargs.get("section"),
                "layout_modes": list(kwargs.get("layout_modes") or []),
                "count_options": list(kwargs.get("count_options") or []),
                "spacing_options": list(kwargs.get("spacing_options") or []),
                "dia_options": list(kwargs.get("dia_options") or []),
                "single_column": kwargs.get("single_column"),
                "sec_shape": kwargs.get("sec_shape"),
            }
        )

    def fast_get_param(key: str, default: Any = None) -> Any:
        events.append({"fn": "fast_get_param", "key": key, "default": default})
        return {"rowgap_bot": 68.0, "cover_bot": 42.0}.get(key, default)

    def number_row(*args: Any, **kwargs: Any) -> None:
        sync_arg = args[3] if len(args) > 3 and isinstance(args[3], dict) else {}
        events.append(
            {
                "fn": "number_row",
                "args": list(args[:3]),
                "sync_keys": sorted(sync_arg.keys()),
                "kwargs": dict(kwargs),
            }
        )

    originals = {
        "st": module.st,
        "info_i_button": module.info_i_button,
        "audit": module._longitudinal_reo_widget_audit_snapshot,
        "widget_key": module.get_widget_key_for_shared,
        "seed": module.seed_widget_from_shared,
        "row_config": module.render_longitudinal_reo_row_config_controls,
        "recommendation_panel": module._render_bottom_recommendation_panel,
        "agent_debug": module._agent_debug_log,
        "reo_rows": module.render_longitudinal_reo_rows,
        "number_row": module.number_row,
    }
    try:
        module.st = SimpleNamespace(
            session_state=session_state,
            columns=columns,
            markdown=markdown,
            subheader=subheader,
            divider=divider,
            button=button,
            caption=caption,
        )
        module.info_i_button = info_i_button
        module._longitudinal_reo_widget_audit_snapshot = audit
        module.get_widget_key_for_shared = widget_key
        module.seed_widget_from_shared = seed
        module.render_longitudinal_reo_row_config_controls = row_config
        module._render_bottom_recommendation_panel = recommendation_panel
        module._agent_debug_log = agent_debug
        module.render_longitudinal_reo_rows = reo_rows
        module.number_row = number_row
        result = module.render_inputs_bottom_reinforcement_column_current_coordinator(
            col_bot_reo=_ContextRecorder(events, "bottom-column"),
            inputs_detailed_mode=inputs_detailed_mode,
            sync_callbacks={"sync_a": object()},
            fast_get_param=fast_get_param,
            sec_shape_reo_ui="T" if is_ti else "RECT",
            is_ti_reo_ui=is_ti,
            bot_hdr="Bottom reinforcement",
        )
    finally:
        module.st = originals["st"]
        module.info_i_button = originals["info_i_button"]
        module._longitudinal_reo_widget_audit_snapshot = originals["audit"]
        module.get_widget_key_for_shared = originals["widget_key"]
        module.seed_widget_from_shared = originals["seed"]
        module.render_longitudinal_reo_row_config_controls = originals["row_config"]
        module._render_bottom_recommendation_panel = originals["recommendation_panel"]
        module._agent_debug_log = originals["agent_debug"]
        module.render_longitudinal_reo_rows = originals["reo_rows"]
        module.number_row = originals["number_row"]

    return {"events": events, "result": result}


def _run_flange_side(module: Any, *, sec_shape: str, mirror_top: bool, mirror_bot: bool) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    session_state: dict[str, Any] = {
        "sec_shape": sec_shape,
        "top_flange_mirror_lr": mirror_top,
        "bot_flange_mirror_lr": mirror_bot,
    }

    def columns(spec: Any, **kwargs: Any) -> tuple[_ContextRecorder, _ContextRecorder]:
        count = spec if isinstance(spec, int) else len(spec)
        events.append({"fn": "columns", "spec": spec, "kwargs": dict(kwargs)})
        return tuple(_ContextRecorder(events, f"flange-col-{idx}") for idx in range(int(count)))

    def markdown(text: str, **kwargs: Any) -> None:
        events.append({"fn": "markdown", "text": str(text), "kwargs": dict(kwargs)})

    def caption(text: str, **kwargs: Any) -> None:
        events.append({"fn": "caption", "text": str(text), "kwargs": dict(kwargs)})

    def fast_get_param(key: str, default: Any = None) -> Any:
        events.append({"fn": "fast_get_param", "key": key, "default": default})
        return default

    def select_row(*args: Any, **kwargs: Any) -> None:
        sync_arg = args[4] if len(args) > 4 and isinstance(args[4], dict) else {}
        options = args[2] if len(args) > 2 else None
        if isinstance(options, dict):
            options_shape: Any = {"keys": list(options.keys()), "values": list(options.values())}
        else:
            options_shape = list(options or [])
        events.append(
            {
                "fn": "select_row",
                "label": args[0] if len(args) > 0 else None,
                "key": args[1] if len(args) > 1 else None,
                "options": options_shape,
                "value": args[3] if len(args) > 3 else None,
                "sync_keys": sorted(sync_arg.keys()),
                "kwargs": dict(kwargs),
            }
        )

    def number_row(*args: Any, **kwargs: Any) -> None:
        sync_arg = args[3] if len(args) > 3 and isinstance(args[3], dict) else {}
        events.append(
            {
                "fn": "number_row",
                "args": list(args[:3]),
                "sync_keys": sorted(sync_arg.keys()),
                "kwargs": dict(kwargs),
            }
        )

    originals = {
        "st": module.st,
        "select_row": module.select_row,
        "number_row": module.number_row,
    }
    try:
        module.st = SimpleNamespace(
            session_state=session_state,
            columns=columns,
            markdown=markdown,
            caption=caption,
        )
        module.select_row = select_row
        module.number_row = number_row
        result = module.render_inputs_flange_reinforcement_current_coordinator(
            sync_callbacks={"sync_a": object()},
            fast_get_param=fast_get_param,
        )
    finally:
        module.st = originals["st"]
        module.select_row = originals["select_row"]
        module.number_row = originals["number_row"]

    return {"events": events, "result": result}


def _run_shear_side(
    module: Any,
    *,
    inputs_detailed_mode: bool,
    fast_focus_section: str | None,
    corrected_invalid_shear_state: bool,
    load_pressed: bool,
    dev_mode: bool,
    shared: dict[str, Any],
    widgets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    session_state: dict[str, Any] = {
        "active_beam_id": "B1",
        "page_slug": "inputs",
        "_dev_mode": dev_mode,
        **shared,
        **dict(widgets or {}),
    }

    def columns(spec: Any, **kwargs: Any) -> tuple[_ContextRecorder, _ContextRecorder]:
        events.append({"fn": "columns", "spec": list(spec), "kwargs": dict(kwargs)})
        return (
            _ContextRecorder(events, "header-title"),
            _ContextRecorder(events, "header-info"),
        )

    def markdown(text: str, **kwargs: Any) -> None:
        events.append({"fn": "markdown", "text": str(text), "kwargs": dict(kwargs)})

    def subheader(text: str, **kwargs: Any) -> None:
        events.append({"fn": "subheader", "text": str(text), "kwargs": dict(kwargs)})

    def divider() -> None:
        events.append({"fn": "divider"})

    def button(label: str, **kwargs: Any) -> bool:
        events.append({"fn": "button", "label": label, "kwargs": dict(kwargs)})
        return load_pressed

    def caption(text: str, **kwargs: Any) -> None:
        events.append({"fn": "caption", "text": str(text), "kwargs": dict(kwargs)})

    def info_i_button(**kwargs: Any) -> _ContextRecorder:
        events.append({"fn": "info_i_button", "kwargs": dict(kwargs)})
        return _ContextRecorder(events, "info")

    def shared_state_snapshot() -> dict[str, Any]:
        snapshot = {
            "lig_d": session_state.get("lig_d"),
            "lig_legs": session_state.get("lig_legs"),
            "s_lig": session_state.get("s_lig"),
        }
        events.append({"fn": "shared_state_snapshot", "snapshot": dict(snapshot)})
        return snapshot

    def widget_key(shared_key: str, *, prefix: str = "") -> str:
        events.append({"fn": "widget_key", "shared_key": shared_key, "prefix": prefix})
        return f"{prefix}{shared_key}"

    def seed(widget_key_value: str, shared_key: str, default: Any) -> None:
        events.append(
            {
                "fn": "seed",
                "widget_key": widget_key_value,
                "shared_key": shared_key,
                "default": default,
            }
        )
        session_state.setdefault(widget_key_value, session_state.get(shared_key, default))

    def shear_recommendation_panel(**kwargs: Any) -> None:
        events.append({"fn": "shear_recommendation_panel", "kwargs": dict(kwargs)})

    def agent_debug(message: str, data: dict[str, Any] | None = None, **kwargs: Any) -> None:
        events.append(
            {
                "fn": "agent_debug",
                "message": message,
                "data": data,
                "kwargs": dict(kwargs),
            }
        )

    def select_row(*args: Any, **kwargs: Any) -> None:
        sync_arg = args[4] if len(args) > 4 and isinstance(args[4], dict) else {}
        options = args[2] if len(args) > 2 else None
        if isinstance(options, dict):
            options_shape: Any = {"keys": list(options.keys()), "values": list(options.values())}
        else:
            options_shape = list(options or [])
        events.append(
            {
                "fn": "select_row",
                "label": args[0] if len(args) > 0 else None,
                "key": args[1] if len(args) > 1 else None,
                "options": options_shape,
                "value": args[3] if len(args) > 3 else None,
                "sync_keys": sorted(sync_arg.keys()),
                "kwargs": dict(kwargs),
            }
        )

    def number_row(*args: Any, **kwargs: Any) -> None:
        sync_arg = args[3] if len(args) > 3 and isinstance(args[3], dict) else {}
        events.append(
            {
                "fn": "number_row",
                "args": list(args[:3]),
                "sync_keys": sorted(sync_arg.keys()),
                "kwargs": dict(kwargs),
            }
        )

    originals = {
        "st": module.st,
        "info_i_button": module.info_i_button,
        "shared_state": module._shared_state_snapshot,
        "widget_key": module.get_widget_key_for_shared,
        "seed": module.seed_widget_from_shared,
        "shear_recommendation_panel": module._render_shear_recommendation_panel,
        "agent_debug": module._agent_debug_log,
        "select_row": module.select_row,
        "number_row": module.number_row,
    }
    try:
        module.st = SimpleNamespace(
            session_state=session_state,
            columns=columns,
            markdown=markdown,
            subheader=subheader,
            divider=divider,
            button=button,
            caption=caption,
        )
        module.info_i_button = info_i_button
        module._shared_state_snapshot = shared_state_snapshot
        module.get_widget_key_for_shared = widget_key
        module.seed_widget_from_shared = seed
        module._render_shear_recommendation_panel = shear_recommendation_panel
        module._agent_debug_log = agent_debug
        module.select_row = select_row
        module.number_row = number_row
        result = module.render_inputs_shear_reinforcement_column_current_coordinator(
            col_shear_mat=_ContextRecorder(events, "shear-column"),
            inputs_detailed_mode=inputs_detailed_mode,
            fast_focus_section=fast_focus_section,
            corrected_invalid_shear_state=corrected_invalid_shear_state,
            sync_callbacks={"sync_a": object()},
        )
    finally:
        module.st = originals["st"]
        module.info_i_button = originals["info_i_button"]
        module._shared_state_snapshot = originals["shared_state"]
        module.get_widget_key_for_shared = originals["widget_key"]
        module.seed_widget_from_shared = originals["seed"]
        module._render_shear_recommendation_panel = originals["shear_recommendation_panel"]
        module._agent_debug_log = originals["agent_debug"]
        module.select_row = originals["select_row"]
        module.number_row = originals["number_row"]

    return {
        "events": events,
        "result": result,
        "seed_consume_audit": session_state.get("_inputs_shear_seed_consume_audit"),
        "truth_audit": session_state.get("_inputs_shear_truth_audit"),
    }


def _run_support_side(module: Any, *, inputs_detailed_mode: bool, session_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    session_state: dict[str, Any] = {
        "active_beam_id": "B1",
        "page_slug": "inputs",
        **dict(session_overrides or {}),
    }

    def columns(spec: Any, **kwargs: Any) -> tuple[_ContextRecorder, ...]:
        count = spec if isinstance(spec, int) else len(spec)
        events.append({"fn": "columns", "spec": spec, "kwargs": dict(kwargs)})
        return tuple(_ContextRecorder(events, f"support-col-{idx}") for idx in range(int(count)))

    def subheader(text: str, **kwargs: Any) -> None:
        events.append({"fn": "subheader", "text": str(text), "kwargs": dict(kwargs)})

    def selectbox(label: str, options: Any, **kwargs: Any) -> Any:
        events.append(
            {
                "fn": "selectbox",
                "label": label,
                "options": list(options or []),
                "kwargs": {
                    key: value
                    for key, value in kwargs.items()
                    if key not in {"on_change", "format_func"}
                },
                "has_on_change": callable(kwargs.get("on_change")),
                "has_format_func": callable(kwargs.get("format_func")),
            }
        )
        index = int(kwargs.get("index", 0) or 0)
        option_list = list(options or [])
        return option_list[index] if option_list else None

    def page_divider() -> None:
        events.append({"fn": "page_divider"})

    def materials(sync_callbacks: dict[str, Any]) -> None:
        events.append({"fn": "materials", "sync_keys": sorted(sync_callbacks.keys())})

    def time_dependent(sync_callbacks: dict[str, Any]) -> None:
        events.append({"fn": "time_dependent", "sync_keys": sorted(sync_callbacks.keys())})

    def ducts(sync_callbacks: dict[str, Any]) -> None:
        events.append({"fn": "ducts", "sync_keys": sorted(sync_callbacks.keys())})

    def label_with_hover(label: str, hover_md: str | None = None, **kwargs: Any) -> None:
        events.append(
            {
                "fn": "label_with_hover",
                "label": label,
                "hover_md": hover_md,
                "kwargs": dict(kwargs),
            }
        )

    def number_row(*args: Any, **kwargs: Any) -> None:
        sync_arg = args[3] if len(args) > 3 and isinstance(args[3], dict) else {}
        events.append(
            {
                "fn": "number_row",
                "args": list(args[:3]),
                "sync_keys": sorted(sync_arg.keys()),
                "kwargs": dict(kwargs),
            }
        )

    def fast_get_param(key: str, default: Any = None) -> Any:
        events.append({"fn": "fast_get_param", "key": key, "default": default})
        return {"exposure_class": "C1"}.get(key, default)

    def mark(label: str) -> None:
        events.append({"fn": "mark", "label": label})

    def sub_mark(label: str) -> None:
        events.append({"fn": "sub_mark", "label": label})

    originals = {
        "st": module.st,
        "page_divider": module.page_divider,
        "materials": module._render_materials_and_sectionA_2d,
        "time_dependent": module._render_time_dependent_inputs,
        "ducts": module._render_ducts_prestress_voids_inputs,
        "label_with_hover": module.label_with_hover,
        "number_row": module.number_row,
    }
    try:
        module.st = SimpleNamespace(
            session_state=session_state,
            columns=columns,
            subheader=subheader,
            selectbox=selectbox,
        )
        module.page_divider = page_divider
        module._render_materials_and_sectionA_2d = materials
        module._render_time_dependent_inputs = time_dependent
        module._render_ducts_prestress_voids_inputs = ducts
        module.label_with_hover = label_with_hover
        module.number_row = number_row
        result = module.render_inputs_detailed_support_lower_row_current_coordinator(
            inputs_detailed_mode=inputs_detailed_mode,
            sync_callbacks={
                "inputs_exposure_class": object(),
                "inputs_crack_member_type": object(),
                "inputs_crack_k1": object(),
                "inputs_crack_k2": object(),
            },
            fast_get_param=fast_get_param,
            mark=mark,
            sub_mark=sub_mark,
        )
    finally:
        module.st = originals["st"]
        module.page_divider = originals["page_divider"]
        module._render_materials_and_sectionA_2d = originals["materials"]
        module._render_time_dependent_inputs = originals["time_dependent"]
        module._render_ducts_prestress_voids_inputs = originals["ducts"]
        module.label_with_hover = originals["label_with_hover"]
        module.number_row = originals["number_row"]

    return {"events": events, "result": result}


def _run_geometry_side(
    module: Any,
    *,
    inputs_detailed_mode: bool,
    sec_shape: str,
    load_pressed: bool,
    right_diagram_present: bool,
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    session_state: dict[str, Any] = {
        "active_beam_id": "B1",
        "page_slug": "inputs",
        "sec_shape": sec_shape,
        "inputs_sec_shape": sec_shape,
    }

    def container() -> _ContextRecorder:
        events.append({"fn": "container"})
        return _ContextRecorder(events, "st-container")

    def markdown(text: str, **kwargs: Any) -> None:
        events.append({"fn": "markdown", "text": str(text), "kwargs": dict(kwargs)})

    def header(
        title: str,
        *,
        help_text: str,
        level: str,
        render_popover_content,
        render_popover_always=None,
    ) -> None:
        events.append(
            {
                "fn": "header",
                "title": title,
                "help_text": help_text,
                "level": level,
                "has_always": render_popover_always is not None,
            }
        )
        if render_popover_always is not None:
            render_popover_always()
        if load_pressed:
            render_popover_content()

    def geometry_recommendation(**kwargs: Any) -> None:
        events.append({"fn": "geometry_recommendation", "kwargs": dict(kwargs)})

    def select_row(*args: Any, **kwargs: Any) -> None:
        sync_arg = args[4] if len(args) > 4 and isinstance(args[4], dict) else {}
        events.append(
            {
                "fn": "select_row",
                "label": args[0] if len(args) > 0 else None,
                "key": args[1] if len(args) > 1 else None,
                "options": list(args[2] if len(args) > 2 else []),
                "value": args[3] if len(args) > 3 else None,
                "sync_keys": sorted(sync_arg.keys()),
                "kwargs": dict(kwargs),
            }
        )

    def number_row(*args: Any, **kwargs: Any) -> None:
        sync_arg = args[3] if len(args) > 3 and isinstance(args[3], dict) else {}
        events.append(
            {
                "fn": "number_row",
                "args": list(args[:3]),
                "sync_keys": sorted(sync_arg.keys()),
                "kwargs": dict(kwargs),
            }
        )

    def fast_get_param(key: str, default: Any = None) -> Any:
        values = {
            "D": 610.0,
            "L": 3200.0,
            "cover_side": 45.0,
            "b": 410.0,
            "bf": 650.0,
            "tf": 130.0,
            "bw": 310.0,
            "tw": 220.0,
        }
        events.append({"fn": "fast_get_param", "key": key, "default": default})
        return values.get(key, default)

    def materials(sync_callbacks: dict[str, Any], *, show_heading: bool = True) -> None:
        events.append(
            {
                "fn": "materials",
                "show_heading": show_heading,
                "sync_keys": sorted(sync_callbacks.keys()),
            }
        )

    def section_diagram(**kwargs: Any) -> None:
        events.append({"fn": "section_diagram", "kwargs": dict(kwargs)})

    def model_state() -> tuple[dict[str, Any], dict[str, Any]]:
        events.append({"fn": "model_state"})
        return (
            {
                "shear_truth_governing_check_name": "Shear check",
                "shear_truth_governing_reason": "governing",
            },
            {
                "model_overlay_lig_d": 10,
                "model_overlay_lig_legs": 2,
                "model_overlay_s_lig": 150.0,
            },
        )

    def fast_model(sync_callbacks: dict[str, Any], model_state: dict[str, Any] | None = None) -> None:
        events.append(
            {
                "fn": "fast_model",
                "sync_keys": sorted(sync_callbacks.keys()),
                "model_state": dict(model_state or {}),
            }
        )

    def page_divider() -> None:
        events.append({"fn": "page_divider"})

    def mark(label: str) -> None:
        events.append({"fn": "mark", "label": label})

    def sub_mark(label: str) -> None:
        events.append({"fn": "sub_mark", "label": label})

    originals = {
        "st": module.st,
        "header": module._render_recommendation_section_header,
        "geometry_recommendation": module._render_geometry_recommendation_panel,
        "select_row": module.select_row,
        "number_row": module.number_row,
        "materials": module._render_inputs_materials_subsection,
        "section_diagram": getattr(module, "_render_section_2d_diagram_block", None),
        "section_diagram_direct": module.render_inputs_section_2d_diagram_block,
        "model_state": module._resolved_inputs_model_state,
        "fast_model": getattr(module, "_render_fast_model_block", None),
        "fast_model_direct": module.render_inputs_fast_model_block,
        "page_divider": module.page_divider,
    }
    try:
        module.st = SimpleNamespace(
            session_state=session_state,
            container=container,
            markdown=markdown,
        )
        module._render_recommendation_section_header = header
        module._render_geometry_recommendation_panel = geometry_recommendation
        module.select_row = select_row
        module.number_row = number_row
        module._render_inputs_materials_subsection = materials
        module._render_section_2d_diagram_block = section_diagram
        module.render_inputs_section_2d_diagram_block = (
            lambda **kwargs: section_diagram()
            if kwargs.get("compact", False) is False and kwargs.get("model_state") is None
            else section_diagram(
                compact=kwargs.get("compact", False),
                model_state=kwargs.get("model_state"),
            )
        )
        module._resolved_inputs_model_state = model_state
        module._render_fast_model_block = fast_model
        module.render_inputs_fast_model_block = lambda **kwargs: fast_model(
            kwargs.get("sync_callbacks") or {},
            model_state=kwargs.get("model_state"),
        )
        module.page_divider = page_divider
        result = module.render_inputs_geometry_materials_top_section_current_coordinator(
            geometry_slot=_ContextRecorder(events, "geometry-slot"),
            right_diagram=_ContextRecorder(events, "right-diagram") if right_diagram_present else None,
            model_slot=_ContextRecorder(events, "model-slot"),
            inputs_detailed_mode=inputs_detailed_mode,
            sync_callbacks={"sync_a": object()},
            fast_get_param=fast_get_param,
            mark=mark,
            sub_mark=sub_mark,
        )
    finally:
        module.st = originals["st"]
        module._render_recommendation_section_header = originals["header"]
        module._render_geometry_recommendation_panel = originals["geometry_recommendation"]
        module.select_row = originals["select_row"]
        module.number_row = originals["number_row"]
        module._render_inputs_materials_subsection = originals["materials"]
        if originals["section_diagram"] is None:
            delattr(module, "_render_section_2d_diagram_block")
        else:
            module._render_section_2d_diagram_block = originals["section_diagram"]
        module._resolved_inputs_model_state = originals["model_state"]
        if originals["fast_model"] is None:
            delattr(module, "_render_fast_model_block")
        else:
            module._render_fast_model_block = originals["fast_model"]
        module.render_inputs_section_2d_diagram_block = originals["section_diagram_direct"]
        module.render_inputs_fast_model_block = originals["fast_model_direct"]
        module.page_divider = originals["page_divider"]

    return {
        "events": events,
        "result": result,
        "fast_model_state_debug": session_state.get("_inputs_fast_model_state_debug"),
    }


def _run_simple_helper_side(module: Any, *, helper_name: str, session_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    session_state: dict[str, Any] = {
        "active_beam_id": "B1",
        "page_slug": "inputs",
        **dict(session_overrides or {}),
    }

    def subheader(text: str, **kwargs: Any) -> None:
        events.append({"fn": "subheader", "text": text, "kwargs": dict(kwargs)})

    def get_param_stub(key: str, default: Any = None) -> Any:
        values = {
            "t_shrink": 400.0,
            "t_creep": 500.0,
            "age_at_loading": 35.0,
            "n_ducts": 2.0,
            "duct_dia": 75.0,
        }
        events.append({"fn": "get_param", "key": key, "default": default})
        return values.get(key, default)

    def widget_key(shared_key: str, *, prefix: str = "") -> str:
        events.append({"fn": "widget_key", "shared_key": shared_key, "prefix": prefix})
        return f"{prefix}{shared_key}"

    def number_row(*args: Any, **kwargs: Any) -> None:
        sync_arg = args[3] if len(args) > 3 and isinstance(args[3], dict) else {}
        events.append(
            {
                "fn": "number_row",
                "args": list(args[:3]),
                "sync_keys": sorted(sync_arg.keys()),
                "kwargs": dict(kwargs),
            }
        )

    def select_row(*args: Any, **kwargs: Any) -> None:
        sync_arg = args[4] if len(args) > 4 and isinstance(args[4], dict) else {}
        events.append(
            {
                "fn": "select_row",
                "label": args[0] if len(args) > 0 else None,
                "key": args[1] if len(args) > 1 else None,
                "options": list(args[2] if len(args) > 2 else []),
                "value": args[3] if len(args) > 3 else None,
                "sync_keys": sorted(sync_arg.keys()),
                "kwargs": dict(kwargs),
            }
        )

    originals = {
        "st": module.st,
        "get_param": module.get_param,
        "get_widget_key_for_shared": module.get_widget_key_for_shared,
        "number_row": module.number_row,
        "select_row": module.select_row,
    }
    try:
        module.st = SimpleNamespace(session_state=session_state, subheader=subheader)
        module.get_param = get_param_stub
        module.get_widget_key_for_shared = widget_key
        module.number_row = number_row
        module.select_row = select_row
        result = getattr(module, helper_name)({"sync_a": object()})
    finally:
        module.st = originals["st"]
        module.get_param = originals["get_param"]
        module.get_widget_key_for_shared = originals["get_widget_key_for_shared"]
        module.number_row = originals["number_row"]
        module.select_row = originals["select_row"]

    return {"events": events, "result": result}


def _run_materials_helper_side(
    module: Any,
    *,
    show_heading: bool,
    session_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    session_state: dict[str, Any] = {
        "active_beam_id": "B1",
        "page_slug": "inputs",
        **dict(session_overrides or {}),
    }

    def subheader(text: str, **kwargs: Any) -> None:
        events.append({"fn": "subheader", "text": text, "kwargs": dict(kwargs)})

    def get_param_stub(key: str, default: Any = None) -> Any:
        values = {"fsy": 500.0, "fc": 40.0}
        events.append({"fn": "get_param", "key": key, "default": default})
        return values.get(key, default)

    def widget_key(shared_key: str, *, prefix: str = "") -> str:
        events.append({"fn": "widget_key", "shared_key": shared_key, "prefix": prefix})
        return f"{prefix}{shared_key}"

    def number_row(*args: Any, **kwargs: Any) -> None:
        sync_arg = args[3] if len(args) > 3 and isinstance(args[3], dict) else {}
        events.append(
            {
                "fn": "number_row",
                "args": list(args[:3]),
                "sync_keys": sorted(sync_arg.keys()),
                "kwargs": dict(kwargs),
            }
        )

    originals = {
        "st": module.st,
        "get_param": module.get_param,
        "get_widget_key_for_shared": module.get_widget_key_for_shared,
        "number_row": module.number_row,
    }
    try:
        module.st = SimpleNamespace(session_state=session_state, subheader=subheader)
        module.get_param = get_param_stub
        module.get_widget_key_for_shared = widget_key
        module.number_row = number_row
        result = module._render_inputs_materials_subsection(
            {"sync_a": object()},
            show_heading=show_heading,
        )
    finally:
        module.st = originals["st"]
        module.get_param = originals["get_param"]
        module.get_widget_key_for_shared = originals["get_widget_key_for_shared"]
        module.number_row = originals["number_row"]

    return {"events": events, "result": result}


def _run_materials_sectionA_side(
    module: Any,
    *,
    design_controls: bool,
    session_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    session_state: dict[str, Any] = {
        "active_beam_id": "B1",
        "page_slug": "inputs",
        "member_faces_exposed": "invalid face value",
        "shrinkage_env": "Interior environment",
        "env_option": "Arid environment",
        "d_g": 22.0,
        "k_v_method": "Simplified non-prestressed (Cl. 8.2.4.3)",
        **dict(session_overrides or {}),
    }

    def columns(spec: Any, **kwargs: Any) -> tuple[_ContextRecorder, _ContextRecorder]:
        events.append({"fn": "columns", "spec": list(spec), "kwargs": dict(kwargs)})
        return (_ContextRecorder(events, "materials"), _ContextRecorder(events, "sectionA"))

    def subheader(text: str, **kwargs: Any) -> None:
        events.append({"fn": "subheader", "text": text, "kwargs": dict(kwargs)})

    def info(text: str, **kwargs: Any) -> None:
        events.append({"fn": "info", "text": text, "kwargs": dict(kwargs)})

    def markdown(text: str, **kwargs: Any) -> None:
        events.append({"fn": "markdown", "text": text, "kwargs": dict(kwargs)})

    def widget_key(shared_key: str, *, prefix: str = "") -> str:
        events.append({"fn": "widget_key", "shared_key": shared_key, "prefix": prefix})
        return f"{prefix}{shared_key}"

    def select_row(*args: Any, **kwargs: Any) -> None:
        sync_arg = args[4] if len(args) > 4 and isinstance(args[4], dict) else {}
        events.append(
            {
                "fn": "select_row",
                "args": list(args[:4]),
                "sync_keys": sorted(sync_arg.keys()),
                "kwargs": dict(kwargs),
            }
        )

    def number_row(*args: Any, **kwargs: Any) -> None:
        sync_arg = args[3] if len(args) > 3 and isinstance(args[3], dict) else {}
        events.append(
            {
                "fn": "number_row",
                "args": list(args[:3]),
                "sync_keys": sorted(sync_arg.keys()),
                "kwargs": dict(kwargs),
            }
        )

    def is_governing() -> bool:
        events.append({"fn": "is_design_governing"})
        return design_controls

    def resolve_support() -> dict[str, Any]:
        events.append({"fn": "resolve_support_defaults"})
        return {
            "support_current": "Simply supported",
            "support_options": ["Simply supported", "Continuous"],
            "defl_limit_val": 250,
            "defl_limit_options_by_ratio": {250: "L/250", 500: "L/500"},
        }

    def caption_deflection() -> None:
        events.append({"fn": "caption_deflection_limit"})

    def render_3d() -> None:
        events.append({"fn": "render_3d"})

    originals = {
        "st": module.st,
        "get_widget_key_for_shared": module.get_widget_key_for_shared,
        "select_row": module.select_row,
        "number_row": module.number_row,
        "is_design_governing": module.is_design_governing,
        "resolve_support": module._resolve_inputs_support_and_deflection_defaults,
        "caption": module._caption_inputs_deflection_limit_ratio,
        "render_3d": getattr(module, "_render_3d_diagram_block", None),
        "render_3d_direct": module.render_inputs_3d_diagram_block,
    }
    try:
        module.st = SimpleNamespace(
            session_state=session_state,
            columns=columns,
            subheader=subheader,
            info=info,
            markdown=markdown,
        )
        module.get_widget_key_for_shared = widget_key
        module.select_row = select_row
        module.number_row = number_row
        module.is_design_governing = is_governing
        module._resolve_inputs_support_and_deflection_defaults = resolve_support
        module._caption_inputs_deflection_limit_ratio = caption_deflection
        module._render_3d_diagram_block = render_3d
        module.render_inputs_3d_diagram_block = lambda **kwargs: render_3d()
        result = module._render_materials_and_sectionA_2d({"sync_a": object()})
    finally:
        module.st = originals["st"]
        module.get_widget_key_for_shared = originals["get_widget_key_for_shared"]
        module.select_row = originals["select_row"]
        module.number_row = originals["number_row"]
        module.is_design_governing = originals["is_design_governing"]
        module._resolve_inputs_support_and_deflection_defaults = originals["resolve_support"]
        module._caption_inputs_deflection_limit_ratio = originals["caption"]
        if originals["render_3d"] is None:
            delattr(module, "_render_3d_diagram_block")
        else:
            module._render_3d_diagram_block = originals["render_3d"]
        module.render_inputs_3d_diagram_block = originals["render_3d_direct"]

    return {"events": events, "result": result}


def _run_landing_card_side(module: Any, *, pressed_key: str | None) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    session_state: dict[str, Any] = {"page_slug": "inputs"}

    def markdown(text: str, **kwargs: Any) -> None:
        events.append({"fn": "markdown", "text": text.strip(), "kwargs": dict(kwargs)})

    def columns(spec: Any, **kwargs: Any) -> tuple[_ContextRecorder, _ContextRecorder]:
        events.append({"fn": "columns", "spec": spec, "kwargs": dict(kwargs)})
        return (_ContextRecorder(events, "landing-left"), _ContextRecorder(events, "landing-right"))

    def button(label: str, **kwargs: Any) -> bool:
        key = kwargs.get("key")
        pressed = key == pressed_key
        events.append({"fn": "button", "label": label, "kwargs": dict(kwargs), "pressed": pressed})
        return pressed

    def rerun() -> None:
        events.append({"fn": "rerun"})

    def sync_callbacks() -> dict[str, Any]:
        events.append({"fn": "get_sync_callbacks"})
        return {"sync": "callback"}

    originals = {
        "st": module.st,
        "get_sync_callbacks": module.get_sync_callbacks,
    }
    try:
        module.st = SimpleNamespace(
            session_state=session_state,
            markdown=markdown,
            columns=columns,
            button=button,
            rerun=rerun,
        )
        module.get_sync_callbacks = sync_callbacks
        try:
            result = module.render_landing_card(sync_callbacks=None)
        except TypeError as exc:
            if "st_module" not in str(exc):
                raise
            result = module.render_landing_card(sync_callbacks=None, st_module=module.st)
    finally:
        module.st = originals["st"]
        module.get_sync_callbacks = originals["get_sync_callbacks"]
    return {"events": events, "result": result, "session_after": dict(session_state)}


def _run_fast_model_block_side(module: Any, *, show_3d: bool, model_state: dict[str, Any]) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    session_state: dict[str, Any] = {
        "active_beam_id": "B1",
        "page_slug": "inputs",
        "b": 400.0,
        "D": 600.0,
        "keep_key": "keep",
    }

    def columns(spec: Any, **kwargs: Any) -> tuple[_ContextRecorder, _ContextRecorder]:
        events.append({"fn": "columns", "spec": list(spec), "kwargs": dict(kwargs)})
        return (
            _ContextRecorder(events, "model-title"),
            _ContextRecorder(events, "model-toggle"),
        )

    def markdown(text: str, **kwargs: Any) -> None:
        events.append({"fn": "markdown", "text": text, "kwargs": dict(kwargs)})

    def shared_toggle(*args: Any, **kwargs: Any) -> bool:
        sync_arg = args[4] if len(args) > 4 and isinstance(args[4], dict) else {}
        events.append(
            {
                "fn": "shared_toggle",
                "args": list(args[:4]),
                "sync_keys": sorted(sync_arg.keys()),
                "kwargs": dict(kwargs),
            }
        )
        return show_3d

    def render_3d(**kwargs: Any) -> None:
        events.append(
            {
                "fn": "render_3d",
                "kwargs": dict(kwargs),
                "session_during_render": {
                    "b": session_state.get("b"),
                    "D": session_state.get("D"),
                    "temporary_only": session_state.get("temporary_only"),
                    "keep_key": session_state.get("keep_key"),
                },
            }
        )

    def render_2d(**kwargs: Any) -> None:
        events.append(
            {
                "fn": "render_2d",
                "kwargs": dict(kwargs),
                "session_during_render": {
                    "b": session_state.get("b"),
                    "D": session_state.get("D"),
                    "temporary_only": session_state.get("temporary_only"),
                    "keep_key": session_state.get("keep_key"),
                },
            }
        )

    originals = {
        "st": module.st,
        "shared_toggle": module._shared_toggle,
        "render_3d": getattr(module, "_render_3d_diagram_block", None),
        "render_2d": getattr(module, "_render_section_2d_diagram_block", None),
    }
    try:
        module.st = SimpleNamespace(
            session_state=session_state,
            columns=columns,
            markdown=markdown,
        )
        module._shared_toggle = shared_toggle
        module._render_3d_diagram_block = render_3d
        module._render_section_2d_diagram_block = render_2d
        if hasattr(module, "_render_fast_model_block"):
            result = module._render_fast_model_block(
                {"sync_a": object()},
                model_state=model_state,
            )
        else:
            from inputs_page_modules.diagrams import render_inputs_fast_model_block

            result = render_inputs_fast_model_block(
                st_module=module.st,
                sync_callbacks={"sync_a": object()},
                model_state=model_state,
                shared_toggle_fn=module._shared_toggle,
                render_with_temporary_model_state_fn=module._render_with_temporary_model_state,
                render_3d_diagram_block_fn=module._render_3d_diagram_block,
                render_section_2d_diagram_block_fn=module._render_section_2d_diagram_block,
            )
    finally:
        module.st = originals["st"]
        module._shared_toggle = originals["shared_toggle"]
        if originals["render_3d"] is None:
            delattr(module, "_render_3d_diagram_block")
        else:
            module._render_3d_diagram_block = originals["render_3d"]
        if originals["render_2d"] is None:
            delattr(module, "_render_section_2d_diagram_block")
        else:
            module._render_section_2d_diagram_block = originals["render_2d"]

    return {
        "events": events,
        "result": result,
        "session_after": dict(session_state),
    }


class _FakeFigure:
    def __init__(self, events: list[dict[str, Any]], label: str) -> None:
        self._events = events
        self._label = label

    def __deepcopy__(self, memo: dict[int, Any]) -> "_FakeFigure":
        self._events.append({"fn": "fig_deepcopy", "label": self._label})
        return self

    def update_layout(self, **kwargs: Any) -> None:
        self._events.append({"fn": "fig_update_layout", "label": self._label, "kwargs": dict(kwargs)})


def _run_section_2d_side(
    module: Any,
    *,
    compact: bool,
    session_overrides: dict[str, Any],
    cached: bool,
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    session_state: dict[str, Any] = {
        "active_beam_id": "B1",
        "page_slug": "inputs",
        "sec_shape": "RECT",
        "b": 400.0,
        "D": 600.0,
        **dict(session_overrides),
    }
    if cached:
        fp = tuple((key, session_state.get(key)) for key in sorted(module.MODEL_RENDER_FINGERPRINT_KEYS))
        session_state["_inputs_model_2d_geo_fp"] = fp
        session_state["_inputs_model_2d_fig"] = _FakeFigure(events, "cached")

    def perf_counter() -> float:
        events.append({"fn": "perf_counter"})
        return 1.0

    def info(text: str, **kwargs: Any) -> None:
        events.append({"fn": "info", "text": text, "kwargs": dict(kwargs)})

    def warning(text: str, **kwargs: Any) -> None:
        events.append({"fn": "warning", "text": text, "kwargs": dict(kwargs)})

    def exception(exc: BaseException) -> None:
        events.append({"fn": "exception", "type": type(exc).__name__, "message": str(exc)})

    def expander(label: str, **kwargs: Any) -> _ContextRecorder:
        events.append({"fn": "expander", "label": label, "kwargs": dict(kwargs)})
        return _ContextRecorder(events, "expander")

    def markdown(text: str, **kwargs: Any) -> None:
        events.append({"fn": "markdown", "text": text, "kwargs": dict(kwargs)})

    def plotly_chart(fig: Any, **kwargs: Any) -> None:
        events.append({"fn": "plotly_chart", "fig_label": getattr(fig, "_label", None), "kwargs": dict(kwargs)})

    def make_summary() -> _FakeFigure:
        events.append({"fn": "make_summary"})
        return _FakeFigure(events, "fresh")

    originals = {
        "st": module.st,
        "time": module.time,
        "make_summary_cross_section_figure": module.make_summary_cross_section_figure,
        "render_plotly_diagram": getattr(module, "render_plotly_diagram", None),
    }
    try:
        module.st = SimpleNamespace(
            session_state=session_state,
            info=info,
            warning=warning,
            exception=exception,
            expander=expander,
            markdown=markdown,
            plotly_chart=plotly_chart,
        )
        module.time = SimpleNamespace(perf_counter=perf_counter)
        module.make_summary_cross_section_figure = make_summary
        if hasattr(module, "render_plotly_diagram"):
            module.render_plotly_diagram = plotly_chart
        if hasattr(module, "_render_section_2d_diagram_block"):
            result = module._render_section_2d_diagram_block(compact=compact)
        else:
            from inputs_page_modules.diagrams import render_inputs_section_2d_diagram_block

            result = render_inputs_section_2d_diagram_block(
                st_module=module.st,
                compact=compact,
                model_state=None,
                time_perf_counter_fn=module.time.perf_counter,
                inputs_geometry_fingerprint_fn=module._inputs_geometry_fingerprint,
                make_summary_cross_section_figure_fn=module.make_summary_cross_section_figure,
                copy_deepcopy_fn=module.copy.deepcopy,
                render_plotly_diagram_fn=(
                    module.render_plotly_diagram
                    if hasattr(module, "render_plotly_diagram")
                    else plotly_chart
                ),
            )
    finally:
        module.st = originals["st"]
        module.time = originals["time"]
        module.make_summary_cross_section_figure = originals["make_summary_cross_section_figure"]
        if originals["render_plotly_diagram"] is None and hasattr(module, "render_plotly_diagram"):
            delattr(module, "render_plotly_diagram")
        elif originals["render_plotly_diagram"] is not None:
            module.render_plotly_diagram = originals["render_plotly_diagram"]

    sanitized_session = {
        key: value
        for key, value in session_state.items()
        if key not in {"_inputs_model_2d_fig"}
    }
    sanitized_session["_inputs_model_2d_fig_label"] = getattr(session_state.get("_inputs_model_2d_fig"), "_label", None)
    return {"events": events, "result": result, "session_after": sanitized_session}


def _run_section_3d_side(
    module: Any,
    *,
    compact: bool,
    shape_name: str,
    cached: bool,
    model_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    session_state: dict[str, Any] = {
        "active_beam_id": "B1",
        "page_slug": "inputs",
        "sec_shape": "T" if shape_name.startswith("T-Section") else "RECT",
        "b": 400.0,
        "D": 600.0,
    }
    fp_source = model_state if isinstance(model_state, dict) else session_state
    if cached:
        fp = tuple((key, fp_source.get(key)) for key in sorted(module.MODEL_RENDER_FINGERPRINT_KEYS))
        session_state["_inputs_model_3d_cache"] = {
            "geo_fp": fp,
            "shape_name": shape_name,
            "fig": _FakeFigure(events, "cached-3d"),
        }

    def perf_counter() -> float:
        events.append({"fn": "perf_counter"})
        return 2.0

    def markdown(text: str, **kwargs: Any) -> None:
        events.append({"fn": "markdown", "text": text.strip(), "kwargs": dict(kwargs)})

    def plotly_chart(fig: Any, **kwargs: Any) -> None:
        events.append({"fn": "plotly_chart", "fig_label": getattr(fig, "_label", None), "kwargs": dict(kwargs)})

    def compute_layout() -> dict[str, Any]:
        events.append({"fn": "compute_layout"})
        return {
            "shape_name": shape_name,
            "dims": {"b": 400.0, "D": 600.0, "bf": 600.0, "tf": 120.0, "bw": 300.0},
            "reo": {"lig_d": 8.0, "lig_legs": 2, "s_lig": 200.0},
            "reo_layout": {"top": [], "bottom": []},
        }

    def shared_state() -> dict[str, Any]:
        events.append({"fn": "shared_state"})
        return {"lig_d": 10.0, "lig_legs": 2, "s_lig": 175.0}

    def cached_make_section_3d_figure(**kwargs: Any) -> _FakeFigure:
        events.append({"fn": "cached_make_section_3d_figure", "kwargs": dict(kwargs)})
        return _FakeFigure(events, "section-3d")

    def make_beam_3d_figure() -> _FakeFigure:
        events.append({"fn": "make_beam_3d_figure"})
        return _FakeFigure(events, "beam-3d")

    originals = {
        "st": module.st,
        "time": module.time,
        "compute_section_layout": module.compute_section_layout,
        "shared_state": module._shared_state_snapshot,
        "cached_make_section_3d_figure": module.cached_make_section_3d_figure,
        "make_beam_3d_figure": module.make_beam_3d_figure,
        "render_plotly_diagram": getattr(module, "render_plotly_diagram", None),
    }
    try:
        module.st = SimpleNamespace(
            session_state=session_state,
            markdown=markdown,
            plotly_chart=plotly_chart,
        )
        module.time = SimpleNamespace(perf_counter=perf_counter)
        module.compute_section_layout = compute_layout
        module._shared_state_snapshot = shared_state
        module.cached_make_section_3d_figure = cached_make_section_3d_figure
        module.make_beam_3d_figure = make_beam_3d_figure
        if hasattr(module, "render_plotly_diagram"):
            module.render_plotly_diagram = plotly_chart
        if hasattr(module, "_render_3d_diagram_block"):
            result = module._render_3d_diagram_block(compact=compact, model_state=model_state)
        else:
            from inputs_page_modules.diagrams import render_inputs_3d_diagram_block

            result = render_inputs_3d_diagram_block(
                st_module=module.st,
                compact=compact,
                model_state=model_state,
                time_perf_counter_fn=module.time.perf_counter,
                inputs_geometry_fingerprint_fn=module._inputs_geometry_fingerprint,
                copy_deepcopy_fn=module.copy.deepcopy,
                compute_section_layout_fn=module.compute_section_layout,
                shared_state_snapshot_fn=module._shared_state_snapshot,
                cache_json_fn=module._cache_json,
                cached_make_section_3d_figure_fn=module.cached_make_section_3d_figure,
                make_beam_3d_figure_fn=module.make_beam_3d_figure,
                render_plotly_diagram_fn=(
                    module.render_plotly_diagram
                    if hasattr(module, "render_plotly_diagram")
                    else plotly_chart
                ),
            )
    finally:
        module.st = originals["st"]
        module.time = originals["time"]
        module.compute_section_layout = originals["compute_section_layout"]
        module._shared_state_snapshot = originals["shared_state"]
        module.cached_make_section_3d_figure = originals["cached_make_section_3d_figure"]
        module.make_beam_3d_figure = originals["make_beam_3d_figure"]
        if originals["render_plotly_diagram"] is None and hasattr(module, "render_plotly_diagram"):
            delattr(module, "render_plotly_diagram")
        elif originals["render_plotly_diagram"] is not None:
            module.render_plotly_diagram = originals["render_plotly_diagram"]

    cache_payload = dict(session_state.get("_inputs_model_3d_cache") or {})
    cache_payload["fig_label"] = getattr(cache_payload.get("fig"), "_label", None)
    cache_payload.pop("fig", None)
    return {"events": events, "result": result, "cache_after": cache_payload}


def _run_geometry_fingerprint_side(module: Any, state: dict[str, Any] | None) -> dict[str, Any]:
    original_st = module.st
    try:
        module.st = SimpleNamespace(session_state={"b": 400.0, "D": 600.0, "lig_d": 10})
        result = module._inputs_geometry_fingerprint(state)
    finally:
        module.st = original_st
    return {"result": result}


def _run_resolved_model_state_side(
    module: Any,
    *,
    session_overrides: dict[str, Any],
    pack_raises: bool,
) -> dict[str, Any]:
    session_state: dict[str, Any] = {
        "page_slug": "inputs",
        "inputs_bot_row_count": 2,
        **copy.deepcopy(session_overrides),
    }
    summary_state = {
        "sec_shape": "RECT",
        "b": 400.0,
        "D": 600.0,
        "cover_bot": 40.0,
        "cover_top": 40.0,
        "cover_side": 40.0,
        "bot_row_count": 1,
        "bot_row_1_bars": 3,
        "bot_row_1_dia": 20.0,
        "bot1_count": 3,
        "db_bot_1": 20.0,
        "lig_d": 10.0,
        "lig_legs": 2,
        "s_lig": 200.0,
    }
    summary_debug = {
        "summary_overlay_s_lig": 200.0,
        "summary_overlay_lig_d": 10.0,
        "summary_overlay_lig_legs": 2,
        "summary_shared_only_mode": False,
        "summary_shared_only_reason": None,
    }
    events: list[dict[str, Any]] = []

    def resolved_summary_state() -> tuple[dict[str, Any], dict[str, Any]]:
        events.append({"fn": "resolved_summary_state"})
        return copy.deepcopy(summary_state), copy.deepcopy(summary_debug)

    def canonical_pack(state: dict[str, Any]) -> dict[str, Any]:
        events.append(
            {
                "fn": "canonical_pack",
                "bot_row_1_bars": state.get("bot_row_1_bars"),
                "bot_row_1_dia": state.get("bot_row_1_dia"),
            }
        )
        if pack_raises:
            raise RuntimeError("forced pack failure")
        return {
            "canonical_pack_valid": True,
            "bot_bar_coords": ["packed-bot"],
            "top_bar_coords": ["packed-top"],
        }

    canonical_name = (
        "_build_canonical_design_state_pack"
        if hasattr(module, "_build_canonical_design_state_pack")
        else "_build_canonical_design_state_pack_for_app_bridge"
    )
    originals = {
        "st": module.st,
        "resolved_summary": module._resolved_inputs_summary_state,
        "canonical_pack": getattr(module, canonical_name),
    }
    try:
        module.st = SimpleNamespace(session_state=session_state)
        module._resolved_inputs_summary_state = resolved_summary_state
        setattr(module, canonical_name, canonical_pack)
        model_state, debug_payload = module._resolved_inputs_model_state()
    finally:
        module.st = originals["st"]
        module._resolved_inputs_summary_state = originals["resolved_summary"]
        setattr(module, canonical_name, originals["canonical_pack"])
    return {
        "events": events,
        "model_state_subset": {
            key: copy.deepcopy(model_state.get(key))
            for key in (
                "bot_row_1_bars",
                "bot_row_1_dia",
                "bot1_count",
                "db_bot_1",
                "bot_bar_coords",
                "top_bar_coords",
                "canonical_pack_valid",
            )
        },
        "debug_subset": {
            key: copy.deepcopy(debug_payload.get(key))
            for key in (
                "model_state_source",
                "fast_model_uses_overlay_state",
                "fast_model_reo_widget_overlay_applied",
                "fast_model_reo_widget_overlay_count",
                "fast_model_reo_widget_overlay_keys",
                "fast_model_reo_widget_overlay_pack_failed",
            )
        },
    }


def main() -> int:
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route_bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    cases: dict[str, dict[str, Any]] = {}
    checks: dict[str, bool] = {}
    reference_module = legacy_inputs_page
    reference_is_legacy = hasattr(
        legacy_inputs_page,
        "render_inputs_top_section_layout_slots_coordinator",
    )
    if not reference_is_legacy:
        reference_module = route_bridge

    for case_name, inputs_detailed_mode, sec_shape in (
        ("fast_rect", False, "RECT"),
        ("detailed_t", True, "T"),
    ):
        legacy_result = _run_side(
            reference_module,
            legacy=reference_is_legacy,
            inputs_detailed_mode=inputs_detailed_mode,
            sec_shape=sec_shape,
        )
        bridge_result = _run_side(
            route_bridge,
            legacy=False,
            inputs_detailed_mode=inputs_detailed_mode,
            sec_shape=sec_shape,
        )
        cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}
        checks[f"{case_name}_events_match_legacy"] = legacy_result["events"] == bridge_result["events"]
        checks[f"{case_name}_return_matches_legacy"] = legacy_result["result"] == bridge_result["result"]

    top_column_cases: dict[str, dict[str, Any]] = {}
    for case_name, load_pressed, is_ti in (
        ("top_popover_closed_rect", False, False),
        ("top_popover_loaded_ti", True, True),
    ):
        legacy_result = _run_top_column_side(
            reference_module,
            load_pressed=load_pressed,
            is_ti=is_ti,
        )
        bridge_result = _run_top_column_side(
            route_bridge,
            load_pressed=load_pressed,
            is_ti=is_ti,
        )
        top_column_cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}
        checks[f"{case_name}_events_match_legacy"] = legacy_result["events"] == bridge_result["events"]
        checks[f"{case_name}_return_matches_legacy"] = legacy_result["result"] == bridge_result["result"]

    bottom_column_cases: dict[str, dict[str, Any]] = {}
    for case_name, load_pressed, is_ti, inputs_detailed_mode, dev_mode in (
        ("bottom_popover_closed_rect", False, False, False, False),
        ("bottom_popover_loaded_ti_dev", True, True, True, True),
    ):
        legacy_result = _run_bottom_column_side(
            reference_module,
            load_pressed=load_pressed,
            is_ti=is_ti,
            inputs_detailed_mode=inputs_detailed_mode,
            dev_mode=dev_mode,
        )
        bridge_result = _run_bottom_column_side(
            route_bridge,
            load_pressed=load_pressed,
            is_ti=is_ti,
            inputs_detailed_mode=inputs_detailed_mode,
            dev_mode=dev_mode,
        )
        bottom_column_cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}
        checks[f"{case_name}_events_match_legacy"] = legacy_result["events"] == bridge_result["events"]
        checks[f"{case_name}_return_matches_legacy"] = legacy_result["result"] == bridge_result["result"]

    flange_cases: dict[str, dict[str, Any]] = {}
    for case_name, sec_shape, mirror_top, mirror_bot in (
        ("flange_rect_noop", "RECT", True, True),
        ("flange_t_mirrored", "T", True, True),
        ("flange_i_unmirrored", "I", False, False),
    ):
        legacy_result = _run_flange_side(
            reference_module,
            sec_shape=sec_shape,
            mirror_top=mirror_top,
            mirror_bot=mirror_bot,
        )
        bridge_result = _run_flange_side(
            route_bridge,
            sec_shape=sec_shape,
            mirror_top=mirror_top,
            mirror_bot=mirror_bot,
        )
        flange_cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}
        checks[f"{case_name}_events_match_legacy"] = legacy_result["events"] == bridge_result["events"]
        checks[f"{case_name}_return_matches_legacy"] = legacy_result["result"] == bridge_result["result"]

    shear_cases: dict[str, dict[str, Any]] = {}
    for case_name, payload in {
        "shear_fast_hint_closed": {
            "inputs_detailed_mode": False,
            "fast_focus_section": "shear",
            "corrected_invalid_shear_state": False,
            "load_pressed": False,
            "dev_mode": False,
            "shared": {"lig_d": 10, "lig_legs": 2, "s_lig": 150.0},
            "widgets": {},
        },
        "shear_corrected_loaded_dev": {
            "inputs_detailed_mode": True,
            "fast_focus_section": None,
            "corrected_invalid_shear_state": True,
            "load_pressed": True,
            "dev_mode": True,
            "shared": {"lig_d": 12, "lig_legs": 2, "s_lig": 175.0},
            "widgets": {},
        },
        "shear_stale_widgets_no_links": {
            "inputs_detailed_mode": False,
            "fast_focus_section": None,
            "corrected_invalid_shear_state": False,
            "load_pressed": False,
            "dev_mode": False,
            "shared": {"lig_d": 0, "lig_legs": 0, "s_lig": 200.0},
            "widgets": {"inputs_lig_d": 12, "inputs_lig_legs": 2, "inputs_s_lig": 150.0},
        },
    }.items():
        legacy_result = _run_shear_side(reference_module, **payload)
        bridge_result = _run_shear_side(route_bridge, **payload)
        shear_cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}
        checks[f"{case_name}_events_match_legacy"] = legacy_result["events"] == bridge_result["events"]
        checks[f"{case_name}_return_matches_legacy"] = legacy_result["result"] == bridge_result["result"]
        checks[f"{case_name}_seed_audit_matches_legacy"] = (
            legacy_result["seed_consume_audit"] == bridge_result["seed_consume_audit"]
        )
        checks[f"{case_name}_truth_audit_matches_legacy"] = (
            legacy_result["truth_audit"] == bridge_result["truth_audit"]
        )

    support_cases: dict[str, dict[str, Any]] = {}
    for case_name, inputs_detailed_mode, session_overrides in (
        ("support_fast_mode", False, {}),
        (
            "support_detailed_existing_exposure_tension",
            True,
            {
                "inputs_exposure_class": "B2",
                "crack_member_type": "Primarily tension",
                "crack_k1": 1.6,
                "crack_k2": 1.0,
            },
        ),
        (
            "support_detailed_seeded_defaults",
            True,
            {
                "crack_member_type": "Primarily flexure",
                "crack_k1": 0.8,
            },
        ),
    ):
        legacy_result = _run_support_side(
            reference_module,
            inputs_detailed_mode=inputs_detailed_mode,
            session_overrides=session_overrides,
        )
        bridge_result = _run_support_side(
            route_bridge,
            inputs_detailed_mode=inputs_detailed_mode,
            session_overrides=session_overrides,
        )
        support_cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}
        checks[f"{case_name}_events_match_legacy"] = legacy_result["events"] == bridge_result["events"]
        checks[f"{case_name}_return_matches_legacy"] = legacy_result["result"] == bridge_result["result"]

    geometry_cases: dict[str, dict[str, Any]] = {}
    for case_name, inputs_detailed_mode, sec_shape, load_pressed, right_diagram_present in (
        ("geometry_fast_rect_loaded", False, "RECT", True, False),
        ("geometry_detailed_t_with_diagram", True, "T", False, True),
        ("geometry_detailed_i_without_diagram_loaded", True, "I", True, False),
    ):
        legacy_result = _run_geometry_side(
            reference_module,
            inputs_detailed_mode=inputs_detailed_mode,
            sec_shape=sec_shape,
            load_pressed=load_pressed,
            right_diagram_present=right_diagram_present,
        )
        bridge_result = _run_geometry_side(
            route_bridge,
            inputs_detailed_mode=inputs_detailed_mode,
            sec_shape=sec_shape,
            load_pressed=load_pressed,
            right_diagram_present=right_diagram_present,
        )
        geometry_cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}
        checks[f"{case_name}_events_match_legacy"] = legacy_result["events"] == bridge_result["events"]
        checks[f"{case_name}_return_matches_legacy"] = legacy_result["result"] == bridge_result["result"]
        checks[f"{case_name}_fast_model_debug_matches_legacy"] = (
            legacy_result["fast_model_state_debug"] == bridge_result["fast_model_state_debug"]
        )

    helper_cases: dict[str, dict[str, Any]] = {}
    for case_name, helper_name, session_overrides in (
        ("time_dependent_defaults", "_render_time_dependent_inputs", {}),
        (
            "time_dependent_existing_widgets",
            "_render_time_dependent_inputs",
            {
                "inputs_t_shrink": 410.0,
                "inputs_t_creep": 510.0,
                "inputs_age_at_loading": 36.0,
            },
        ),
        ("ducts_defaults", "_render_ducts_prestress_voids_inputs", {}),
        (
            "ducts_existing_widgets",
            "_render_ducts_prestress_voids_inputs",
            {
                "inputs_n_ducts": 3.0,
                "inputs_duct_dia": 80.0,
                "k_d_option": "Prestressing ducts present (apply k_d)",
            },
        ),
    ):
        legacy_result = _run_simple_helper_side(
            reference_module,
            helper_name=helper_name,
            session_overrides=session_overrides,
        )
        bridge_result = _run_simple_helper_side(
            route_bridge,
            helper_name=helper_name,
            session_overrides=session_overrides,
        )
        helper_cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}
        checks[f"{case_name}_events_match_legacy"] = legacy_result["events"] == bridge_result["events"]
        checks[f"{case_name}_return_matches_legacy"] = legacy_result["result"] == bridge_result["result"]

    materials_cases: dict[str, dict[str, Any]] = {}
    for case_name, show_heading, session_overrides in (
        ("materials_with_heading_defaults", True, {}),
        ("materials_no_heading_existing_widgets", False, {"inputs_fsy": 600.0, "inputs_fc": 50.0}),
    ):
        legacy_result = _run_materials_helper_side(
            reference_module,
            show_heading=show_heading,
            session_overrides=session_overrides,
        )
        bridge_result = _run_materials_helper_side(
            route_bridge,
            show_heading=show_heading,
            session_overrides=session_overrides,
        )
        materials_cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}
        checks[f"{case_name}_events_match_legacy"] = legacy_result["events"] == bridge_result["events"]
        checks[f"{case_name}_return_matches_legacy"] = legacy_result["result"] == bridge_result["result"]

    materials_sectionA_cases: dict[str, dict[str, Any]] = {}
    for case_name, design_controls, session_overrides in (
        ("materials_sectionA_design_controlled", True, {}),
        (
            "materials_sectionA_manual_existing_values",
            False,
            {
                "member_faces_exposed": "Column – four faces exposed",
                "shrinkage_env": "Tropical / near-coastal / coastal environment",
                "env_option": "Temperate inland environment",
                "d_g": 16.0,
            },
        ),
    ):
        legacy_result = _run_materials_sectionA_side(
            reference_module,
            design_controls=design_controls,
            session_overrides=session_overrides,
        )
        bridge_result = _run_materials_sectionA_side(
            route_bridge,
            design_controls=design_controls,
            session_overrides=session_overrides,
        )
        materials_sectionA_cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}
        checks[f"{case_name}_events_match_legacy"] = legacy_result["events"] == bridge_result["events"]
        checks[f"{case_name}_return_matches_legacy"] = legacy_result["result"] == bridge_result["result"]

    landing_card_cases: dict[str, dict[str, Any]] = {}
    for case_name, pressed_key in (
        ("landing_card_default", None),
        ("landing_card_go_design_inputs", "inputs_landing_go_design_inputs"),
        ("landing_card_open_design_mode", "inputs_landing_open_detailed"),
    ):
        legacy_result = _run_landing_card_side(reference_module, pressed_key=pressed_key)
        bridge_result = _run_landing_card_side(route_bridge, pressed_key=pressed_key)
        landing_card_cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}
        checks[f"{case_name}_events_match_legacy"] = legacy_result["events"] == bridge_result["events"]
        checks[f"{case_name}_return_matches_legacy"] = legacy_result["result"] == bridge_result["result"]
        checks[f"{case_name}_session_matches_legacy"] = legacy_result["session_after"] == bridge_result["session_after"]

    fast_model_cases: dict[str, dict[str, Any]] = {}
    for case_name, show_3d, model_state in (
        ("fast_model_2d_with_temporary_state", False, {"b": 450.0, "D": 650.0, "temporary_only": "yes"}),
        ("fast_model_3d_with_temporary_state", True, {"b": 460.0, "D": 660.0, "temporary_only": "yes"}),
    ):
        legacy_result = _run_fast_model_block_side(
            reference_module,
            show_3d=show_3d,
            model_state=model_state,
        )
        bridge_result = _run_fast_model_block_side(
            route_bridge,
            show_3d=show_3d,
            model_state=model_state,
        )
        fast_model_cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}
        checks[f"{case_name}_events_match_legacy"] = legacy_result["events"] == bridge_result["events"]
        checks[f"{case_name}_return_matches_legacy"] = legacy_result["result"] == bridge_result["result"]
        checks[f"{case_name}_session_restore_matches_legacy"] = (
            legacy_result["session_after"] == bridge_result["session_after"]
        )

    section_2d_cases: dict[str, dict[str, Any]] = {}
    for case_name, compact, session_overrides, cached in (
        ("section_2d_missing_required", False, {"D": 0.0}, False),
        ("section_2d_fresh_compact", True, {}, False),
        ("section_2d_cached_full", False, {}, True),
    ):
        legacy_result = _run_section_2d_side(
            reference_module,
            compact=compact,
            session_overrides=session_overrides,
            cached=cached,
        )
        bridge_result = _run_section_2d_side(
            route_bridge,
            compact=compact,
            session_overrides=session_overrides,
            cached=cached,
        )
        section_2d_cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}
        checks[f"{case_name}_events_match_legacy"] = legacy_result["events"] == bridge_result["events"]
        checks[f"{case_name}_return_matches_legacy"] = legacy_result["result"] == bridge_result["result"]
        checks[f"{case_name}_session_matches_legacy"] = legacy_result["session_after"] == bridge_result["session_after"]

    section_3d_cases: dict[str, dict[str, Any]] = {}
    for case_name, compact, shape_name, cached, model_state in (
        ("section_3d_rect_fresh", True, "Rectangle (b x D)", False, None),
        ("section_3d_t_fresh", False, "T-Section (bf, tf, bw, D)", False, None),
        ("section_3d_t_cached", False, "T-Section (bf, tf, bw, D)", True, None),
        (
            "section_3d_rect_explicit_model_state",
            True,
            "Rectangle (b x D)",
            False,
            {"b": 410.0, "D": 610.0, "lig_d": 12.0, "lig_legs": 3, "s_lig": 160.0},
        ),
    ):
        legacy_result = _run_section_3d_side(
            reference_module,
            compact=compact,
            shape_name=shape_name,
            cached=cached,
            model_state=model_state,
        )
        bridge_result = _run_section_3d_side(
            route_bridge,
            compact=compact,
            shape_name=shape_name,
            cached=cached,
            model_state=model_state,
        )
        section_3d_cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}
        checks[f"{case_name}_events_match_legacy"] = legacy_result["events"] == bridge_result["events"]
        checks[f"{case_name}_return_matches_legacy"] = legacy_result["result"] == bridge_result["result"]
        checks[f"{case_name}_cache_matches_legacy"] = legacy_result["cache_after"] == bridge_result["cache_after"]

    fingerprint_cases: dict[str, dict[str, Any]] = {}
    for case_name, state in (
        ("fingerprint_session_state", None),
        ("fingerprint_explicit_model_state", {"b": 410.0, "D": 610.0, "lig_d": 12}),
    ):
        legacy_result = _run_geometry_fingerprint_side(reference_module, state)
        bridge_result = _run_geometry_fingerprint_side(route_bridge, state)
        fingerprint_cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}
        checks[f"{case_name}_matches_legacy"] = legacy_result["result"] == bridge_result["result"]

    resolved_model_state_cases: dict[str, dict[str, Any]] = {}
    for case_name, session_overrides, pack_raises in (
        ("resolved_model_state_no_widget_overlay", {}, False),
        (
            "resolved_model_state_widget_overlay_pack_success",
            {"inputs_bot_row_1_bars": 5, "inputs_bot_row_1_dia": 24.0},
            False,
        ),
        (
            "resolved_model_state_widget_overlay_pack_failure",
            {"inputs_bot_row_1_bars": 5, "inputs_bot_row_1_dia": 24.0},
            True,
        ),
    ):
        legacy_result = _run_resolved_model_state_side(
            reference_module,
            session_overrides=session_overrides,
            pack_raises=pack_raises,
        )
        bridge_result = _run_resolved_model_state_side(
            route_bridge,
            session_overrides=session_overrides,
            pack_raises=pack_raises,
        )
        resolved_model_state_cases[case_name] = {"legacy": legacy_result, "bridge": bridge_result}
        checks[f"{case_name}_events_match_legacy"] = legacy_result["events"] == bridge_result["events"]
        checks[f"{case_name}_state_subset_matches_legacy"] = (
            legacy_result["model_state_subset"] == bridge_result["model_state_subset"]
        )
        checks[f"{case_name}_debug_subset_matches_legacy"] = (
            legacy_result["debug_subset"] == bridge_result["debug_subset"]
        )

    bridge_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["widget_sections_uses_local_orchestration"] = (
        "_legacy_inputs_page.render_inputs_widget_sections_current_coordinator" not in bridge_source
    )
    checks["top_reinforcement_uses_local_orchestration"] = (
        "_legacy_inputs_page.render_inputs_top_reinforcement_column_current_coordinator" not in bridge_source
    )
    checks["bottom_reinforcement_uses_local_orchestration"] = (
        "_legacy_inputs_page.render_inputs_bottom_reinforcement_column_current_coordinator" not in bridge_source
    )
    checks["flange_reinforcement_uses_local_orchestration"] = (
        "_legacy_inputs_page.render_inputs_flange_reinforcement_current_coordinator" not in bridge_source
    )
    checks["shear_reinforcement_uses_local_orchestration"] = (
        "_legacy_inputs_page.render_inputs_shear_reinforcement_column_current_coordinator" not in bridge_source
    )
    checks["detailed_support_uses_local_orchestration"] = (
        "_legacy_inputs_page.render_inputs_detailed_support_lower_row_current_coordinator" not in bridge_source
    )
    checks["geometry_materials_uses_local_orchestration"] = (
        "_legacy_inputs_page.render_inputs_geometry_materials_top_section_current_coordinator" not in bridge_source
    )
    checks["time_dependent_helper_uses_local_orchestration"] = (
        "_legacy_inputs_page._render_time_dependent_inputs" not in bridge_source
    )
    checks["ducts_helper_uses_local_orchestration"] = (
        "_legacy_inputs_page._render_ducts_prestress_voids_inputs" not in bridge_source
    )
    checks["materials_subsection_uses_local_orchestration"] = (
        "_legacy_inputs_page._render_inputs_materials_subsection" not in bridge_source
    )
    checks["materials_sectionA_uses_local_orchestration"] = (
        "_legacy_inputs_page._render_materials_and_sectionA_2d" not in bridge_source
    )
    checks["landing_card_uses_local_orchestration"] = (
        "_legacy_inputs_page.render_landing_card" not in bridge_source
    )
    checks["fast_model_block_uses_local_orchestration"] = (
        "_legacy_inputs_page._render_fast_model_block" not in bridge_source
    )
    checks["section_2d_diagram_uses_local_orchestration"] = (
        "_legacy_inputs_page._render_section_2d_diagram_block" not in bridge_source
    )
    checks["section_3d_diagram_uses_local_orchestration"] = (
        "_legacy_inputs_page._render_3d_diagram_block" not in bridge_source
    )
    checks["geometry_fingerprint_uses_local_orchestration"] = (
        "_legacy_inputs_page._inputs_geometry_fingerprint" not in bridge_source
    )
    checks["resolved_inputs_model_state_uses_local_orchestration"] = (
        "_legacy_inputs_page._resolved_inputs_model_state" not in bridge_source
    )
    checks["fast_uses_compact_pair_labels"] = any(
        event == {"fn": "pair_labels", "value": "RECT", "variant": "inputs_compact"}
        for event in cases["fast_rect"]["bridge"]["events"]
    )
    checks["detailed_t_marks_ti_reinforcement"] = any(
        event.get("fn") == "bottom" and event.get("is_ti") is True
        for event in cases["detailed_t"]["bridge"]["events"]
    )

    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_route_widget_sections_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "cases": cases,
        "top_column_cases": top_column_cases,
        "bottom_column_cases": bottom_column_cases,
        "flange_cases": flange_cases,
        "shear_cases": shear_cases,
        "support_cases": support_cases,
        "geometry_cases": geometry_cases,
        "helper_cases": helper_cases,
        "materials_cases": materials_cases,
        "materials_sectionA_cases": materials_sectionA_cases,
        "landing_card_cases": landing_card_cases,
        "fast_model_cases": fast_model_cases,
        "section_2d_cases": section_2d_cases,
        "section_3d_cases": section_3d_cases,
        "fingerprint_cases": fingerprint_cases,
        "resolved_model_state_cases": resolved_model_state_cases,
        "wrapper_note": "route widget sections are local orchestration with explicit legacy helper seams",
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_widget_sections_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_widget_sections_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Widget Sections Parity",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Checks",
                "",
                *(f"- `{name}`: `{passed}`" for name, passed in checks.items()),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
