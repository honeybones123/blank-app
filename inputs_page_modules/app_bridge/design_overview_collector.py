"""Design-overview collection coordination for the Inputs app bridge."""

from __future__ import annotations

from typing import Any


_DESIGN_OVERVIEW_COLLECTOR_DEPENDENCIES: tuple[str, ...] = (
    "_build_bending_check_rows_from_state_for_app_bridge",
    "_build_crack_pack_from_state_for_app_bridge",
    "_build_deflection_pack_from_state_for_app_bridge",
    "_build_design_actions_context_for_app_bridge",
    "_build_shear_check_rows_from_state_for_app_bridge",
    "_overall_status_from_rows",
    "_parse_util_value",
    "_resolve_design_actions_from_state",
    "_stage3_final_published_shear_truth_bundle_for_app_bridge",
    "_stage3_remaining_issue_class_from_overview_state",
    "_state_with_resolved_design_actions_for_app_bridge",
    "stable_fingerprint_for_payload",
    "ux_probe_record",
)


def bind_design_overview_collector_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _DESIGN_OVERVIEW_COLLECTOR_DEPENDENCIES
            if name in namespace
        }
    )


def _collect_design_overview(state: dict, context: dict | None = None) -> dict:
    design_context = context or _build_design_actions_context_for_app_bridge(state)
    overview_state = dict(
        design_context.get("state")
        or _state_with_resolved_design_actions_for_app_bridge(state)
    )
    actions = dict(
        design_context.get("actions") or _resolve_design_actions_from_state(overview_state)
    )
    bend_pack = _build_bending_check_rows_from_state_for_app_bridge(overview_state) or {}
    shear_pack = _build_shear_check_rows_from_state_for_app_bridge(overview_state) or {}
    crack_pack = _build_crack_pack_from_state_for_app_bridge(overview_state)
    defl_pack = _build_deflection_pack_from_state_for_app_bridge(overview_state)

    crack_rows = crack_pack.get("rows") or []
    crack_utils = [_parse_util_value(row.get("util")) for row in crack_rows]
    crack_util_values = [util for util in crack_utils if util is not None]

    def _max_row_util(rows: list[dict] | None) -> float | None:
        values = [
            util
            for util in (_parse_util_value((row or {}).get("util")) for row in list(rows or []))
            if util is not None
        ]
        return max(values) if values else None

    bending_status, _ = _overall_status_from_rows(bend_pack.get("rows") or [])
    shear_status, _ = _overall_status_from_rows(shear_pack.get("rows") or [])
    crack_status, _ = _overall_status_from_rows(crack_rows)
    deflection_status, _ = _overall_status_from_rows(defl_pack.get("rows") or [])

    bending_util = _parse_util_value(bend_pack.get("summary_util"))
    if bending_util is None:
        bending_util = _max_row_util(bend_pack.get("rows") or [])
    shear_util = _parse_util_value(shear_pack.get("summary_util"))
    if shear_util is None:
        shear_util = _max_row_util(
            (shear_pack.get("summary_rows") or [])
            or (shear_pack.get("rows") or []),
        )
    shear_governing_status = str(shear_pack.get("summary_governing_status") or "").strip()
    shear_governing_util = shear_pack.get("summary_governing_util")
    shear_truth_status = str(shear_pack.get("shear_truth_status") or "").strip()
    shear_truth_util = shear_pack.get("shear_truth_util_governing")
    final_shear_truth_resolved = shear_pack.get("final_shear_truth_resolved")
    final_shear_truth_failure_reason = str(
        shear_pack.get("final_shear_truth_failure_reason") or ""
    ).strip()
    if shear_governing_status:
        shear_status = shear_governing_status
    elif shear_truth_status:
        shear_status = shear_truth_status
    elif final_shear_truth_resolved is False or final_shear_truth_failure_reason:
        shear_status = "FAIL"
    if shear_governing_util is not None:
        try:
            shear_util = float(shear_governing_util)
        except Exception:
            pass
    elif shear_truth_util is not None:
        try:
            shear_util = float(shear_truth_util)
        except Exception:
            pass
    crack_util = max(crack_util_values) if crack_util_values else None
    deflection_util = _parse_util_value(defl_pack.get("summary_util_total"))

    statuses = {
        "bending": bending_status,
        "shear": shear_status,
        "crack": crack_status,
        "deflection": deflection_status,
    }
    util_map = {
        "bending": bending_util,
        "shear": shear_util,
        "crack": crack_util,
        "deflection": deflection_util,
    }
    tracked_statuses = [status for status in statuses.values() if status not in ("—", "")]
    any_fail = any(status == "FAIL" for status in tracked_statuses)
    any_warn = any(status == "NEAR LIMIT" for status in tracked_statuses)
    all_key_pass = bool(tracked_statuses) and all(status == "PASS" for status in tracked_statuses)
    worst_util = max((util for util in util_map.values() if util is not None), default=0.0)
    governing_check = None
    governing_source = "overview_worst_util"
    governing_candidates = [
        (check_key, util)
        for check_key, util in util_map.items()
        if util is not None
    ]
    if governing_candidates:
        governing_check, _ = max(governing_candidates, key=lambda item: float(item[1]))
    if governing_check == "shear" and str(shear_pack.get("summary_governing_source") or "").strip():
        governing_source = f"shear:{str(shear_pack.get('summary_governing_source') or '').strip()}"
    overview_out = {
        "packs": {
            "bending": bend_pack,
            "shear": shear_pack,
            "crack": crack_pack,
            "deflection": defl_pack,
        },
        "statuses": statuses,
        "utils": util_map,
        "any_fail": any_fail,
        "any_warn": any_warn,
        "all_key_pass": all_key_pass,
        "worst_util": worst_util,
        "governing_util": worst_util,
        "governing_check": governing_check,
        "governing_util_source": governing_source,
        "actions_used": actions,
        "overview_shear_governing_check_name": shear_pack.get("summary_governing_check_name"),
        "overview_shear_governing_reason": shear_pack.get("summary_governing_reason"),
        "overview_shear_governing_source": shear_pack.get("summary_governing_source"),
        "overview_shear_truth_source": "shear_pack.summary_governing",
        "overview_shear_selection_origin": shear_pack.get("summary_governing_selection_origin"),
    }
    overview_out["stage3_shear_truth_debug"] = (
        _stage3_final_published_shear_truth_bundle_for_app_bridge(overview_state)
    )
    overview_out["design_guide_shear_truth_source"] = "final_published_shear_truth"
    overview_out["stage3_remaining_issue_class"] = _stage3_remaining_issue_class_from_overview_state(
        overview_state,
        overview_out,
    )
    ux_probe_record(
        "inputs_page.summary_overview_build",
        fingerprint=stable_fingerprint_for_payload(
            {
                "state": overview_state,
                "actions": actions,
            }
        ),
        meta={
            "governing_check": governing_check,
            "worst_util": worst_util,
        },
    )
    return overview_out
