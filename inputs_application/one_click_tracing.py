"""Trace payload construction for the Inputs one-click transaction."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
import json
import os
import time
import uuid

from inputs_page_modules.design_guide.trace import (
    append_design_guide_trace as append_design_guide_trace_row,
)


def trace_compact_overview_dict(overview: dict | None) -> dict:
    if not isinstance(overview, dict):
        return {}
    return {
        "worst_util": overview.get("worst_util"),
        "statuses": dict(overview.get("statuses") or {}),
        "all_key_pass": bool(overview.get("all_key_pass")),
    }


def trace_compact_shared_geom_reo(
    state: dict | None,
    *,
    int_from_state: Callable[..., int],
    float_from_state: Callable[..., float],
    bottom_reo_state_label: Callable[[dict], str],
) -> dict:
    if not isinstance(state, dict):
        return {}
    try:
        ligatures = (
            f'{int_from_state(state, "lig_legs", 0)}'
            f'xD{int_from_state(state, "lig_d", 0)}'
            f'@{float_from_state(state, "s_lig", 0.0):.0f}'
        )
    except Exception:
        ligatures = None
    try:
        bottom = bottom_reo_state_label(state)
    except Exception:
        bottom = None
    return {
        "b": state.get("b"),
        "D": state.get("D"),
        "Ast_bot": state.get("Ast_bot"),
        "bottom_label": bottom,
        "ligatures_compact": ligatures,
    }


def design_guide_trace_compare_meta(
    *,
    run_id: str,
    action_signature: str | None,
    goal: str | None,
    starting_worst_util: float | None,
    ending_worst_util: float | None,
    stop_reason: str | None,
    winner_label: str | None,
    final_updates: dict | None,
) -> dict:
    return {
        "run_id": str(run_id),
        "action_signature": action_signature,
        "goal": goal,
        "starting_worst_util": starting_worst_util,
        "ending_worst_util": ending_worst_util,
        "stop_reason": stop_reason,
        "winner_label": winner_label,
        "final_updates": dict(final_updates or {}),
    }


def auto_design_invoke_debug_snapshot(
    *,
    session_state: Mapping[str, object],
    auto_invoke_key: str,
    request_source_key: str,
    request_timestamp_key: str,
) -> dict:
    try:
        return {
            "force_auto_redesign": bool(
                session_state.get("_force_auto_redesign", False)
            ),
            "auto_design_auto_invoke": bool(
                session_state.get(auto_invoke_key, False)
            ),
            "auto_design_request_source": (
                session_state.get("auto_design_request_source")
                or session_state.get(request_source_key)
            ),
            "auto_design_requested_at_ts": session_state.get(
                request_timestamp_key
            ),
            "auto_design_invoke_pending": bool(
                session_state.get("auto_design_invoke_pending", False)
            ),
        }
    except Exception:
        return {
            "force_auto_redesign": None,
            "auto_design_auto_invoke": None,
            "auto_design_request_source": None,
            "auto_design_requested_at_ts": None,
            "auto_design_invoke_pending": None,
        }


def tracer_one_click_action_source_summary(
    trigger_fingerprint: tuple | None,
    *,
    session_state: Mapping[str, object],
    auto_invoke_key: str,
    request_source_key: str,
    request_timestamp_key: str,
) -> dict:
    return {
        "trigger_fingerprint": (
            None
            if trigger_fingerprint is None
            else str(trigger_fingerprint)
        ),
        **auto_design_invoke_debug_snapshot(
            session_state=session_state,
            auto_invoke_key=auto_invoke_key,
            request_source_key=request_source_key,
            request_timestamp_key=request_timestamp_key,
        ),
    }


def agent_debug_log(
    message: str,
    data: dict | None = None,
    *,
    location: str,
    hypothesis_id: str,
    run_id: str = "auto_design_debug",
    log_path: str,
) -> None:
    try:
        timestamp = int(datetime.now().timestamp() * 1000)
        payload = {
            "id": f"log_{timestamp}_{hypothesis_id}",
            "timestamp": timestamp,
            "location": location,
            "message": message,
            "data": data or {},
            "runId": run_id,
            "hypothesisId": hypothesis_id,
        }
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass


def design_guide_tracer_path(*, base_directory: str) -> str:
    override = (
        os.environ.get("DESIGN_GUIDE_TRACER_PATH") or ""
    ).strip()
    if override:
        return override
    return os.path.join(base_directory, "design_guide_tracer.jsonl")


def new_design_guide_trace_run_id(prefix: str = "dg") -> str:
    return f"{prefix}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:10]}"


def design_guide_tracer_verbose_log(
    *,
    session_state: Mapping[str, object],
) -> bool:
    try:
        if bool(session_state.get("_dev_mode")):
            return True
    except Exception:
        pass
    return str(
        os.environ.get("DESIGN_GUIDE_TRACER_DEBUG") or ""
    ).strip().lower() in {"1", "true", "yes", "on"}


def append_design_guide_trace(
    event: str,
    data: dict,
    *,
    run_id: str,
    source: str,
    tracer_path_fn: Callable[[], str],
    tracer_verbose_log_fn: Callable[[], bool],
    agent_debug_log_fn: Callable[..., None],
) -> None:
    append_design_guide_trace_row(
        event,
        data,
        run_id=run_id,
        source=source,
        tracer_path_fn=tracer_path_fn,
        tracer_verbose_log_fn=tracer_verbose_log_fn,
        agent_debug_log_fn=agent_debug_log_fn,
        append_failure_location="inputs_page.py:_append_design_guide_trace",
    )


def stage3_final_published_shear_truth_bundle(
    state: dict | None,
) -> dict:
    keys = (
        "shear_truth_status",
        "shear_truth_reason",
        "shear_truth_governing_check_name",
        "shear_truth_governing_reason",
        "shear_truth_governing_source",
        "final_shear_status_source",
        "final_shear_truth_resolved",
        "final_shear_truth_failure_reason",
        "final_shear_truth_bundle_complete",
        "shear_provided_input_spacing_mm",
        "shear_input_spacing_mm",
        "shear_sectional_check_spacing_mm",
        "shear_effective_spacing_mm",
        "shear_required_spacing_mm",
        "shear_governing_spacing_source",
        "published_result_spacing_mm",
        "published_result_spacing_meaning",
    )
    source = dict(state or {})
    output = {key: source.get(key) for key in keys}
    output["design_guide_shear_truth_source"] = (
        "final_published_shear_truth"
    )
    output["final_shear_truth_normalized_source"] = source.get(
        "_final_shear_truth_normalized_source"
    )
    output["final_shear_truth_normalized_latest"] = dict(
        source.get("_final_shear_truth_normalized_latest") or {}
    )
    return output


__all__ = [
    "auto_design_invoke_debug_snapshot",
    "agent_debug_log",
    "append_design_guide_trace",
    "design_guide_tracer_path",
    "design_guide_tracer_verbose_log",
    "design_guide_trace_compare_meta",
    "trace_compact_overview_dict",
    "trace_compact_shared_geom_reo",
    "tracer_one_click_action_source_summary",
    "new_design_guide_trace_run_id",
    "stage3_final_published_shear_truth_bundle",
]
