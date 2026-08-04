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


def _clear_session() -> None:
    import streamlit as st

    for key in list(st.session_state.keys()):
        st.session_state.pop(key, None)


def _seed_session(values: dict[str, Any]) -> None:
    import streamlit as st

    _clear_session()
    st.session_state.update(copy.deepcopy(values))


def _context_summary(ctx, ss: dict[str, Any]) -> dict[str, Any]:
    adapter = ctx.design_brain_adapter
    return {
        "session_state_matches_passed_ss": dict(ctx.session_state) == dict(ss),
        "beam_order": list(ctx.beam_order or []),
        "active_beam_id": ctx.active_beam_id,
        "beam_labels": dict(ctx.beam_labels or {}),
        "callbacks_present": {
            "set_active_beam": callable(ctx.set_active_beam),
            "add_beam": callable(ctx.add_beam),
            "duplicate_beam": callable(ctx.duplicate_beam),
            "delete_beam": callable(ctx.delete_beam),
            "reset_workspace": callable(ctx.reset_workspace),
            "force_refresh": callable(ctx.force_refresh),
            "log_rerun": callable(ctx.log_rerun),
            "save_active_to_table": callable(ctx.save_active_to_table),
            "apply_resync": callable(ctx.apply_resync),
            "build_schedule_preview_df": callable(ctx.build_schedule_preview_df),
            "build_schedule_editor_df": callable(ctx.build_schedule_editor_df),
            "sync_schedule_editor_df": callable(ctx.sync_schedule_editor_df),
            "build_schedule_export_df": callable(ctx.build_schedule_export_df),
            "get_active_summary": callable(ctx.get_active_summary),
            "format_status_badge": callable(ctx.format_status_badge),
            "format_last_checked": callable(ctx.format_last_checked),
            "make_section_preview_figure": callable(ctx.make_section_preview_figure),
            "render_plotly_diagram": callable(ctx.render_plotly_diagram),
        },
        "adapter_class": type(adapter).__name__,
        "adapter_request_kind": getattr(adapter, "_request_kind", None),
        "adapter_base_state": dict(adapter._base_state_provider()),
    }


def _run_case(module, seed: dict[str, Any]) -> dict[str, Any]:
    import streamlit as st

    calls: list[tuple[str, Any]] = []
    captured: list[Any] = []

    legacy_bridge = getattr(module, "_legacy_inputs_page", module)
    resync_name = (
        "_apply_canonical_convenience_resync_to_shared_for_app_bridge"
        if hasattr(module, "_apply_canonical_convenience_resync_to_shared_for_app_bridge")
        else "_apply_canonical_convenience_resync_to_shared"
    )

    original_render = module.render_batch_design_page
    original_resync = getattr(module, resync_name)
    original_persist = module.persist_active_beam_from_shared
    preview_owner = module if hasattr(module, "make_summary_cross_section_figure") else legacy_bridge
    original_preview = preview_owner.make_summary_cross_section_figure
    original_runner = module._compute_design_guidance_items

    def _render_batch_design_page(ctx):
        calls.append(("render_batch_design_page", type(ctx).__name__))
        captured.append(ctx)

    def _resync(*, source: str):
        calls.append(("apply_resync", source))
        return {"source": source}

    def _persist():
        calls.append(("persist_active_beam_from_shared", None))

    def _preview():
        calls.append(("make_section_preview_figure", None))
        return {"figure": "preview"}

    def _runner(*args, **kwargs):
        calls.append(("design_guidance_runner", kwargs.get("request_kind")))
        return {"passed": True, "utilisation": 0.5}

    try:
        module.render_batch_design_page = _render_batch_design_page
        setattr(module, resync_name, _resync)
        module.persist_active_beam_from_shared = _persist
        preview_owner.make_summary_cross_section_figure = _preview
        module._compute_design_guidance_items = _runner

        _seed_session(seed)
        ss = dict(st.session_state)
        module.render_inputs_batch_design_manager_coordinator(
            ss=ss,
            beam_labels={"B1": "Beam 1"},
            beam_order=["B1", "B2"],
            active_beam_id="B1",
        )
        if not captured:
            raise AssertionError("render_batch_design_page was not called")
        ctx = captured[0]
        context = _context_summary(ctx, ss)
        preview_result = ctx.make_section_preview_figure()
        ctx.save_active_to_table()
        session_after_save = {
            "_beam_skip_auto_persist_once": st.session_state.get("_beam_skip_auto_persist_once")
        }
    finally:
        module.render_batch_design_page = original_render
        setattr(module, resync_name, original_resync)
        module.persist_active_beam_from_shared = original_persist
        preview_owner.make_summary_cross_section_figure = original_preview
        module._compute_design_guidance_items = original_runner

    return {
        "context": context,
        "preview_result": preview_result,
        "session_after_save": session_after_save,
        "calls": calls,
    }


def _run_preview_function(module, *, error_message: str | None = None) -> dict[str, Any]:
    calls: list[tuple[str, Any]] = []

    class _FakeStreamlit:
        def __init__(self) -> None:
            self.session_state: dict[str, Any] = {"active_tension_face": "bottom"}

        def error(self, message):
            calls.append(("st.error", str(message)))

    fake_st = _FakeStreamlit()
    original_st = module.st
    original_compute = module.compute_section_layout
    original_source = module._build_inputs_diagram_source_snapshot
    original_view_model = module.build_inputs_diagram_view_model
    original_trace = module._record_inputs_diagram_view_model_trace
    original_result = module.build_summary_cross_section_result
    original_cached = module.cached_make_section_figure

    layout = {"dims": {"b": 300.0, "D": 600.0}, "reo": {"bars": []}}
    source = SimpleNamespace(layout=layout)
    view_model = SimpleNamespace(
        section_2d=SimpleNamespace(
            tension_face="bottom",
            fallback_cover_side=40.0,
            fallback_cover_top=35.0,
            fallback_cover_bot=45.0,
            display_hash="section-hash",
        ),
        beam_3d=SimpleNamespace(display_hash="beam-hash"),
        display_hash="diagram-hash",
    )

    def _compute_section_layout():
        calls.append(("compute_section_layout", None))
        return layout

    def _source(layout_arg):
        calls.append(("build_inputs_diagram_source_snapshot", dict(layout_arg)))
        return source

    def _view_model(source_arg):
        calls.append(("build_inputs_diagram_view_model", source_arg is source))
        return view_model

    def _trace(source_arg, view_model_arg, *, live_cutover: bool):
        calls.append(("record_inputs_diagram_view_model_trace", source_arg is source, view_model_arg is view_model, bool(live_cutover)))

    def _build_result(**kwargs):
        calls.append(
            (
                "build_summary_cross_section_result",
                kwargs["layout"] is layout,
                kwargs["tension_face"],
                float(kwargs["fallback_cover_side"]),
                float(kwargs["fallback_cover_top"]),
                float(kwargs["fallback_cover_bot"]),
                kwargs["section_figure_builder"] is module.cached_make_section_figure,
            )
        )
        return SimpleNamespace(error_message=error_message, figure={"figure": "section"})

    def _cached_make_section_figure(**kwargs):
        calls.append(("cached_make_section_figure", dict(kwargs)))
        return {"figure": "cached"}

    try:
        module.st = fake_st
        module.compute_section_layout = _compute_section_layout
        module._build_inputs_diagram_source_snapshot = _source
        module.build_inputs_diagram_view_model = _view_model
        module._record_inputs_diagram_view_model_trace = _trace
        module.build_summary_cross_section_result = _build_result
        module.cached_make_section_figure = _cached_make_section_figure
        figure = module.make_summary_cross_section_figure()
    finally:
        module.st = original_st
        module.compute_section_layout = original_compute
        module._build_inputs_diagram_source_snapshot = original_source
        module.build_inputs_diagram_view_model = original_view_model
        module._record_inputs_diagram_view_model_trace = original_trace
        module.build_summary_cross_section_result = original_result
        module.cached_make_section_figure = original_cached

    return {"figure": figure, "calls": calls}


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    import inputs_page_route_coordinators as route

    seed = {
        "active_beam_id": "B1",
        "beam_order": ["B1", "B2"],
        "_beam_skip_auto_persist_once": True,
        "sec_shape": "RECT",
        "b": 300,
        "D": 600,
        "fc": 40,
    }

    routed = _run_case(route, seed)
    preview_function_cases = {
        "normal": _run_preview_function(route),
        "error_message": _run_preview_function(route, error_message="section unavailable"),
    }
    context = routed["context"]

    checks = {
        "context_uses_passed_session_state": context["session_state_matches_passed_ss"],
        "beam_order_preserved": context["beam_order"] == ["B1", "B2"],
        "active_beam_preserved": context["active_beam_id"] == "B1",
        "all_callbacks_present": all(context["callbacks_present"].values()),
        "adapter_is_batch_design_guidance_adapter": context["adapter_class"] == "BatchDesignGuidanceAdapter",
        "adapter_request_kind_is_auto_design": context["adapter_request_kind"] == "auto_design",
        "preview_callback_result_preserved": routed["preview_result"] == {"figure": "preview"},
        "save_callback_clears_skip_autopersist_flag": routed["session_after_save"].get("_beam_skip_auto_persist_once") is False,
        "render_preview_save_call_order_preserved": routed["calls"][:3]
        == [
            ("render_batch_design_page", "BatchDesignPageContext"),
            ("make_section_preview_figure", None),
            ("apply_resync", "beam_manager:save_active_to_table"),
        ]
        and routed["calls"][3:4]
        == [
            ("persist_active_beam_from_shared", None),
        ],
        "preview_function_normal_result_preserved": preview_function_cases["normal"]["figure"] == {"figure": "section"},
        "preview_function_error_is_reported": ("st.error", "section unavailable")
        in preview_function_cases["error_message"]["calls"],
    }
    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(encoding="utf-8")
    checks["route_no_longer_delegates_batch_design_manager"] = (
        "_legacy_inputs_page.render_inputs_batch_design_manager_coordinator" not in route_source
    )
    checks["route_no_longer_uses_legacy_section_preview_figure"] = (
        "_legacy_inputs_page.make_summary_cross_section_figure" not in route_source
    )

    status = "PASS" if all(checks.values()) else "FAIL"
    artifact = {
        "status": status,
        "timestamp": timestamp,
        "checks": checks,
        "route": routed,
        "preview_function_cases": preview_function_cases,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_batch_design_manager_parity_{timestamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_route_batch_design_manager_parity_{timestamp}.md"
    json_path.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Batch Design Manager Parity",
                "",
                f"Status: {status}",
                "",
                "## Checks",
                *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
                "",
                "## Scope",
                "- Verifies the route-local batch manager coordinator after permanent shell cutover.",
                "- Verifies BatchDesignPageContext values, callback presence, save-active callback ordering, preview callback result, and adapter request kind/base-state provider.",
                "- Leaves the mini section preview figure as an explicit diagram/render bridge for a later slice.",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "artifact": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
