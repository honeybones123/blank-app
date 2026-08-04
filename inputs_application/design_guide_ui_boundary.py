"""Neutral UI compatibility boundary for the retired Design Guide renderer.

The V2 card owns Design Guide presentation.  These names remain available to
the legacy rollback renderer, but the legacy modules are imported only when
the explicit ``legacy`` composition binding is selected.
"""

from __future__ import annotations

from importlib import import_module
import os
from pathlib import Path
from typing import Any, Callable, Mapping, MutableMapping

from inputs_application.design_brain_composition import selected_design_brain_adapter_name


DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY = "_design_guide_apply_trace_run_id"
DESIGN_GUIDE_APPLY_TRACE_META_KEY = "_design_guide_apply_trace_meta"


def _legacy() -> bool:
    return selected_design_brain_adapter_name() == "legacy"


def _legacy_attr(module_name: str, attribute: str) -> Any:
    return getattr(import_module(module_name), attribute)


def render_design_guide_panel_orchestration(*args: Any, **kwargs: Any) -> Any:
    if not _legacy():
        return None
    return _legacy_attr(
        "inputs_page_modules.design_guide.panel_orchestration",
        "render_design_guide_panel_orchestration",
    )(*args, **kwargs)


def render_design_guide_debug_sidebar(*args: Any, **kwargs: Any) -> Any:
    if not _legacy():
        return None
    return _legacy_attr(
        "inputs_page_modules.design_guide.debug_sidebar",
        "render_design_guide_debug_sidebar",
    )(*args, **kwargs)


def design_guide_tracer_path() -> str:
    if _legacy():
        return _legacy_attr(
            "inputs_page_modules.design_guide.trace", "design_guide_tracer_path"
        )()
    override = os.environ.get("DESIGN_GUIDE_TRACE_PATH")
    if override:
        return str(override)
    outputs = os.environ.get("BEAM_OUTPUTS_DIR")
    if outputs:
        root = Path(outputs).expanduser().resolve()
    else:
        root = Path(__file__).resolve().parents[2] / "complete-app - Outputs"
    return str(root / "artifacts" / "debug" / "design_guide" / "design_guide_trace.jsonl")


def design_guide_tracer_verbose_log() -> bool:
    if _legacy():
        return _legacy_attr(
            "inputs_page_modules.design_guide.trace", "design_guide_tracer_verbose_log"
        )()
    return str(os.environ.get("DESIGN_GUIDE_TRACER_VERBOSE") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def append_design_guide_trace(
    event: str,
    data: dict,
    *,
    run_id: str,
    source: str,
    tracer_path_fn: Callable[[], str] = design_guide_tracer_path,
    tracer_verbose_log_fn: Callable[[], bool] = design_guide_tracer_verbose_log,
    agent_debug_log_fn: Callable[..., None] | None = None,
    append_failure_location: str = "inputs_application.design_guide_ui_boundary",
) -> None:
    if _legacy():
        return _legacy_attr(
            "inputs_page_modules.design_guide.trace", "append_design_guide_trace"
        )(
            event,
            data,
            run_id=run_id,
            source=source,
            tracer_path_fn=tracer_path_fn,
            tracer_verbose_log_fn=tracer_verbose_log_fn,
            agent_debug_log_fn=agent_debug_log_fn,
            append_failure_location=append_failure_location,
        )
    # V2 has its own publication/job trace.  Keep this compatibility hook
    # deliberately inert so the retired renderer cannot become a dependency.
    return None


def begin_design_guide_apply_trace(
    session_state: MutableMapping[str, Any],
    *,
    recommendation: dict | None,
    source: str,
    append_trace: Callable[..., Any],
) -> str | None:
    if _legacy():
        return _legacy_attr(
            "inputs_page_modules.design_guide.apply_trace_session",
            "begin_design_guide_apply_trace",
        )(
            session_state,
            recommendation=recommendation,
            source=source,
            append_trace=append_trace,
        )
    if not isinstance(recommendation, dict):
        return None
    run_id = f"v2apply_{abs(hash((str(source), str(recommendation.get('candidate_id') or ''))))}"
    session_state[DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY] = run_id
    session_state[DESIGN_GUIDE_APPLY_TRACE_META_KEY] = {
        "run_id": run_id,
        "source": str(source or "design_guide_apply"),
        "action_type": str(recommendation.get("action_type") or "apply_recommendation"),
    }
    return run_id


def end_design_guide_apply_trace(
    session_state: MutableMapping[str, Any],
    *,
    stop_reason: str,
    append_trace: Callable[..., Any],
    final_updates: dict | None = None,
    winner_label: str | None = None,
    **_: Any,
) -> None:
    if _legacy():
        return _legacy_attr(
            "inputs_page_modules.design_guide.apply_trace_session",
            "end_design_guide_apply_trace",
        )(
            session_state,
            stop_reason=stop_reason,
            append_trace=append_trace,
            final_updates=final_updates,
            winner_label=winner_label,
        )
    session_state.pop(DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY, None)
    session_state.pop(DESIGN_GUIDE_APPLY_TRACE_META_KEY, None)


def set_design_guide_live_breadcrumb(
    session_state: MutableMapping[str, Any],
    label: str,
    extra: dict | None = None,
) -> None:
    session_state["_dg_live_breadcrumb"] = {
        "label": str(label),
        "extra": dict(extra or {}),
    }


def should_render_design_guide_slot_from_publication_eligibility(
    *,
    inputs_has_design_actions_or_loads: bool,
    browser_test_mode: bool = False,
    selected_family_id: Any = None,
    active_failures: Any = None,
    invalid_input_state: bool = False,
    blocker_state: bool = False,
    final_publication: Mapping[str, Any] | None = None,
    debug_bundle: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if _legacy():
        return _legacy_attr(
            "inputs_page_modules.design_guide.render_eligibility",
            "should_render_design_guide_slot_from_publication_eligibility",
        )(
            inputs_has_design_actions_or_loads=inputs_has_design_actions_or_loads,
            browser_test_mode=browser_test_mode,
            selected_family_id=selected_family_id,
            active_failures=active_failures,
            invalid_input_state=invalid_input_state,
            blocker_state=blocker_state,
            final_publication=final_publication,
            debug_bundle=debug_bundle,
        )
    publication = dict(final_publication or {})
    cta = dict(publication.get("cta") or {})
    selected_family = str(
        selected_family_id
        or publication.get("selected_family_id")
        or publication.get("published_family_id")
        or cta.get("family")
        or ""
    ).strip()
    outcome_state = str(
        publication.get("outcome_state") or publication.get("status") or ""
    ).strip().upper()
    has_reason = bool(
        selected_family
        or active_failures
        or invalid_input_state
        or blocker_state
        or outcome_state
        or publication.get("publication_hash")
    )
    current_page_gate = bool(browser_test_mode or inputs_has_design_actions_or_loads)
    return {
        "schema": "design_guide_render_eligibility_trace.v1",
        "slot_eligibility_adapter_used": True,
        "slot_eligibility_adapter_product_driving": True,
        "inputs_has_design_actions_or_loads": bool(inputs_has_design_actions_or_loads),
        "browser_test_mode": bool(browser_test_mode),
        "current_page_gate": current_page_gate,
        "contract_required_design_brain_eligibility": has_reason,
        "selected_family_id": selected_family or None,
        "final_publication_outcome_state": outcome_state or None,
        "should_render_design_guide_slot": bool(current_page_gate or has_reason),
        "render_eligibility_reason": "page gate allows render" if current_page_gate else "publication reason allows render",
        "render_eligibility_classification": "A" if current_page_gate else ("C" if has_reason else "B"),
    }


__all__ = [
    "DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY",
    "append_design_guide_trace",
    "begin_design_guide_apply_trace",
    "design_guide_tracer_path",
    "design_guide_tracer_verbose_log",
    "end_design_guide_apply_trace",
    "render_design_guide_debug_sidebar",
    "render_design_guide_panel_orchestration",
    "set_design_guide_live_breadcrumb",
    "should_render_design_guide_slot_from_publication_eligibility",
]
